import os, requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from duckduckgo_search import DDGS

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

PROMPT = """You are ChapterSummarizerBot. NEVER invent plot. You MUST web search first.
Output format: HOOK:... [PAUSE] BEAT1:... BEAT2:... BEAT3:... CLIFFHANGER:... Comment "ARISE" if you'd take it!
140 words max. Manhwa only. If not found: "Chapter not found."
"""

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    with DDGS() as ddgs:
        results = [r["body"] for r in ddgs.text(f"{query} manhwa plot fandom", max_results=3)]
    
    headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
    data = {"model": "gpt-4o-mini", "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": f"Web: {results}\n\nTask: /summary {query}"}]}
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    script = r.json()["choices"][0]["message"]["content"]
    await update.message.reply_text(script)

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("summary", summary))
app.run_polling()
