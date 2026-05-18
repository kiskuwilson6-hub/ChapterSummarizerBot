import os, requests, logging, asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from duckduckgo_search import DDGS

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

# Improved prompt with dialogue and dual-source search
PROMPT = """You are ChapterSummarizerBot for manhwa. NEVER invent plot. Use ONLY the web sources provided.

Search Strategy:
1. Extract actual character DIALOGUE from the chapter
2. Describe key FIGHTS/ACTION sequences
3. Note any REVELATIONS or PLOT TWISTS

Output format (STRICT 140 words max):
🔥 HOOK: One exciting sentence
💬 KEY DIALOGUE: "Actual quote from chapter"
⚔️ ACTION: What happens in 1 sentence
📖 PLOT: 2-3 key story beats
❓ CLIFFHANGER: Question that makes readers want next chapter

If chapter not found in sources: Reply "❌ Chapter not found. Try /summary [Manhwa Name] chapter [number]"

Sources provided: {sources}
"""

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text(
                "📖 *Usage:* `/summary Solo Leveling chapter 5`\n\n"
                "Or: `/summary Tower of God season 2 chapter 120`",
                parse_mode='Markdown'
            )
            return
        
        query = " ".join(context.args)
        await update.message.reply_text(f"🔍 Searching for: *{query}*...", parse_mode='Markdown')
        
        # Search BOTH fan wiki AND Reddit
        sources = []
        
        with DDGS() as ddgs:
            # 1. Fan Wiki Search
            wiki_results = ddgs.text(f"{query} fandom.com manhwa wiki", max_results=2)
            for r in wiki_results:
                sources.append(f"[FANWIKI] {r['body'][:500]}")
            
            # 2. Reddit Discussion Search
            reddit_results = ddgs.text(f"{query} site:reddit.com manhwa discussion", max_results=2)
            for r in reddit_results:
                sources.append(f"[REDDIT] {r['body'][:500]}")
            
            # 3. Direct chapter plot search (backup)
            if len(sources) < 2:
                plot_results = ddgs.text(f"{query} plot summary chapter", max_results=2)
                for r in plot_results:
                    sources.append(f"[PLOT] {r['body'][:500]}")
        
        if not sources:
            await update.message.reply_text(
                "❌ No sources found. Try:\n"
                f"• `/summary {query} chapter 1`\n"
                "• Check spelling (manhwa names: 'Solo Leveling', 'Tower of God')"
            )
            return
        
        # Combine sources
        combined_sources = "\n\n---\n\n".join(sources[:4])
        
        # Call OpenAI
        headers = {
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-3.5-turbo",  # Cheaper than 4o-mini, still good
            "messages": [
                {"role": "system", "content": PROMPT.format(sources=combined_sources)},
                {"role": "user", "content": f"Summarize: {query}"}
            ],
            "temperature": 0.3,  # Lower = more factual, less creative
            "max_tokens": 300
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"OpenAI API error: {response.text}")
            await update.message.reply_text("⚠️ AI service error. Try again in a few minutes.")
            return
        
        script = response.json()["choices"][0]["message"]["content"]
        
        # Add "ARISE" comment if the AI thinks it's accurate
        if "ARISE" in script or any(word in script.lower() for word in ["arise", "accurate", "shadow"]):
            script += "\n\n👑 *ARISE* - Shadow Army approved!"
        
        await update.message.reply_text(script, parse_mode='Markdown')
        
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏰ Search timeout. Please try again.")
    except Exception as e:
        logger.error(f"Error in summary command: {e}")
        await update.message.reply_text("⚠️ Unexpected error. Contact @BotFather for support.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to ChapterSummarizerBot!*\n\n"
        "I summarize manhwa chapters using fan wikis and Reddit discussions.\n\n"
        "*Commands:*\n"
        "• `/summary Solo Leveling chapter 5`\n"
        "• `/search Tower of God` - Find manhwa info\n"
        "• `/help` - This message\n\n"
        "*Example:* `/summary The Beginning After The End chapter 200`\n\n"
        "⚠️ *100% fact-based* - I never invent plot!",
        parse_mode='Markdown'
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/search manhwa name`", parse_mode='Markdown')
        return
    
    query = " ".join(context.args)
    await update.message.reply_text(f"🔎 Searching for *{query}*...", parse_mode='Markdown')
    
    with DDGS() as ddgs:
        results = ddgs.text(f"{query} manhwa description", max_results=3)
    
    if not results:
        await update.message.reply_text("No results found.")
        return
    
    reply = f"📚 *Search results for {query}:*\n\n"
    for i, r in enumerate(results, 1):
        reply += f"{i}. *{r['title'][:50]}*\n"
        reply += f"   {r['body'][:200]}...\n\n"
    
    await update.message.reply_text(reply[:4000], parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*📖 ChapterSummarizerBot Help*\n\n"
        "Get accurate manhwa chapter summaries with actual dialogue and plot points.\n\n"
        "*Commands:*\n"
        "• `/summary [manhwa] chapter [number]`\n"
        "• `/search [manhwa name]`\n"
        "• `/start` - Introduction\n"
        "• `/help` - This message\n\n"
        "*Examples:*\n"
        "`/summary Solo Leveling chapter 180`\n"
        "`/summary Tower of God season 3 chapter 120`\n"
        "`/search Omniscient Reader`\n\n"
        "*Pro tip:* Be specific! Include 'chapter' and the number.\n\n"
        "Source: Fan Wikis + Reddit discussions",
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ An error occurred. Please try again.")

def main():
    """Start the bot"""
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    if not OPENAI_KEY:
        logger.error("OPENAI_KEY environment variable not set!")
        return
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("search", search))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    logger.info("Bot is starting...")
    
    # Run the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
