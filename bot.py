"""
Job Hunter Bot for Noam Shalev
Scans Israeli job boards daily at 10:00 AM (Israel time) and sends
relevant AI/Automation jobs via Telegram.

Run: python3 bot.py
Requires .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from groq import Groq
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from scraper import scrape_all_sites

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────

TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID  = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

SEEN_FILE  = Path("seen_jobs.json")
STATE_FILE = Path("bot_state.json")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Keywords — Track 1 ───────────────────────────────────────────────────────

EN_KEYWORDS = [
    "AI Automation", "Workflow Automation", "No-Code Development", "AI Agents",
    "n8n", "Make", "Prompt Engineering", "RAG", "APIs", "Webhooks",
    "Airtable", "MongoDB", "Qdrant", "Supabase", "GPT", "Claude", "Gemini",
    "CRM Automation", "Business Process Automation", "Process Mapping",
    "Docker", "Cursor", "Python", "LLM", "Digital Transformation", "RPA",
    "Zapier", "Low-Code", "ChatGPT", "Vector Database", "Operations Automation",
    "Machine Learning", "OpenAI", "Langchain", "Anthropic", "Notion Automation",
    "Google Automation", "Automation Specialist", "Integration Engineer",
    "RevOps", "SalesOps", "AI Implementation Specialist", "Chatbot Developer",
    "AI Trainer", "No-Code Consultant", "AI Solutions Engineer",
    "Business Analyst Automation", "Artificial Intelligence", "AI Engineer",
    "AI Developer", "AI Specialist", "AI Consultant", "LLM Engineer",
    "Generative AI", "GenAI", "Embeddings", "Semantic Search",
    "Automation Engineer", "Intelligent Automation", "Workflow Engineer",
    "Integration Specialist", "Systems Integration", "No-Code Developer",
    "Low-Code Developer", "DataOps", "MLOps", "AI Infrastructure",
    "Digital Operations", "Operations Manager", "RevOps Manager",
    "SalesOps Manager", "Growth Operations", "Business Operations", "Tech Lead",
    "Innovation Manager", "HubSpot", "Salesforce", "ActiveCampaign",
    "Monday Automation", "Slack Automation", "Chief of Staff",
    "AI Product Manager", "Technical Project Manager",
]

HE_KEYWORDS = [
    "אוטומציה חכמה", "אוטומציה של תהליכים עסקיים", "פיתוח ללא קוד",
    "סוכני בינה מלאכותית", "הנדסת פרומפטים", "חיפוש סמנטי", "ממשקי API",
    "וובהוק", "ניהול קשרי לקוחות אוטומטי", "מיפוי תהליכים",
    "טרנספורמציה דיגיטלית", "אוטומציה רובוטית", "קוד נמוך",
    "מסד נתונים וקטורי", "אוטומציה תפעולית", "למידת מכונה",
    "מומחה אוטומציה", "מהנדס שילוב מערכות", "מיישם בינה מלאכותית",
    "מפתח צ'אטבוט", "מאמן מודלים", "יועץ ללא קוד",
    "מהנדס פתרונות AI", "אנליסט עסקי ואוטומציה", "בינה מלאכותית",
    "אוטומציה", "גיוס עם AI", "אוטומציה לחנויות", "מפתח אוטומציה",
    "מהנדס אוטומציה", "מומחה בינה מלאכותית", "מפתח AI", "שילוב מערכות",
    "זרימות עבודה", "פיתוח עסקי טכנולוגי", "חדשנות", "פתרונות טכנולוגיות",
    "ניהול תהליכים", "שיווק דיגיטלי", "מנהל תפעול", "מנהל מוצר טכנולוגי",
]

ALL_KEYWORDS = EN_KEYWORDS + HE_KEYWORDS

# ── Groq prompt — Track 2 ────────────────────────────────────────────────────

GROQ_PROMPT = """\
אתה עוזר לנועם שלו, בן 25 מבית דגן, שמחפש עבודה ראשונה בתחום AI & Automation.

רקע מקצועי:
- בוגר קורס AI & No-Code Automation (240 שעות, John Bryce + משרד העבודה)
- ניסיון מעשי: n8n, Make, AI Agents, Multi-Agent Systems, RAG, Prompt Engineering,
  GPT, Claude, Gemini, Groq, Airtable, MongoDB, Qdrant, Supabase, Docker,
  APIs, Webhooks, Base44, Lovable, Cursor, Telegram Bots, Tavily, MySQL, Python

פרויקטים שבנה:
- AI Sales Agent "Max" — סוכן מכירות אוטומטי עם n8n, Airtable, Gmail, GPT
- Multi-Agent AI College CRM — מערכת רב-סוכנים עם RAG, MongoDB, Qdrant
- MAITRE — CRM לרסטורנים עם Base44/Supabase, QR codes, קמפיינים אוטומטיים
- Scopify — כלי SOW אוטומטי עם Claude Sonnet + Supabase, תמחור רב-שכבתי
- אוטומציית חשבוניות — Webhook → Google Docs → PDF → Gmail
- Daily AI Briefing לטלגרם — Tavily + Groq + Gemini
- Telegram Bot עם זיכרון שיחה + Tavily Search
- Movie Semantic Search Agent — n8n + Qdrant + MongoDB
- MySQL Natural Language Agent — שאילתות טבעיות → SQL
- עבודת לקוח — CRM + לידים + WhatsApp + Instagram integration
- Landing Page עם Webhook Integration לאיסוף לידים

ניסיון עסקי:
- מנהל סניף בחנות (קודם לתפקיד בזמן קצר מאוד)
- רכז לוגיסטיקה בשירות לאומי 3 שנים
- רכז יבוא ב-UPS (נוכחי)

מה הוא מחפש:
- משרה מלאה (Full-time) בלבד
- זמינות: מיידי
- מיקום: ישראל (ללא הגבלת אזור) + Remote מחו"ל
- שפות: עברית + אנגלית
- פתוח ל-entry level, לא דורש תואר אקדמי

תחום עבודה:
- AI, אוטומציה, No-Code, דיגיטל, טכנולוגיה, operations
- לוגיקת ההחלטה: "האם נועם יכול להוסיף ערך בתפקיד הזה?"
- אפילו אם רק 50% מתאים — ענה כן. אם יש ספק — ענה כן.

שם המשרה: {title}
חברה: {company}
תיאור: {description}

ענה רק: כן או לא.\
"""

# ── State ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"paused": False, "last_scan": None, "manual_date": None,
            "sent_today": 0, "sent_date": None}

def save_state(s: dict) -> None:
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Seen jobs ────────────────────────────────────────────────────────────────

def load_seen() -> dict:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_seen(seen: dict) -> None:
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")

def clean_seen(seen: dict) -> dict:
    cutoff = datetime.now() - timedelta(days=7)
    return {k: v for k, v in seen.items() if datetime.fromisoformat(v) > cutoff}

def job_hash(job: dict) -> str:
    url   = job.get("url", "")
    title = job.get("title", "")
    co    = job.get("company", "")
    loc   = job.get("location", "")
    desc  = " ".join(job.get("description", "").split()[:20])
    key   = (url + title) if url else (title + co) if co else (title + loc) if loc else (title + desc)
    return hashlib.md5((key + desc + job.get("date", "")).encode()).hexdigest()

# ── Matching ─────────────────────────────────────────────────────────────────

def keyword_match(job: dict) -> bool:
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    return any(kw.lower() in text for kw in ALL_KEYWORDS)

def _groq_check_sync(job: dict) -> bool:
    if not GROQ_KEY:
        return False
    try:
        client = Groq(api_key=GROQ_KEY)
        prompt = GROQ_PROMPT.format(
            title=job.get("title", ""),
            company=job.get("company", ""),
            description=job.get("description", "")[:2000],
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip()
        return "כן" in answer or "yes" in answer.lower()
    except Exception as e:
        log.warning(f"Groq error: {e}")
        return False

async def groq_check(job: dict) -> bool:
    return await asyncio.to_thread(_groq_check_sync, job)

# ── Sending ──────────────────────────────────────────────────────────────────

def fmt_job(job: dict, via: str) -> str:
    desc_words = job.get("description", "").split()
    short = " ".join(desc_words[:40]) + ("..." if len(desc_words) > 40 else "")
    msg = (
        f"🔥 {job.get('title', 'N/A')}\n"
        f"🏢 {job.get('company', 'N/A')} | {job.get('location', 'N/A')}\n"
        f"🎯 נמצא דרך: {via}\n"
        f"📋 {short}\n"
        f"🔗 {job.get('url', '')}"
    )
    return msg[:4090]

async def send_job(app: Application, job: dict, state: dict) -> None:
    via = job.get("_via", "מילות מפתח")
    await app.bot.send_message(chat_id=CHAT_ID, text=fmt_job(job, via),
                               disable_web_page_preview=True)
    today = date.today().isoformat()
    if state.get("sent_date") != today:
        state["sent_today"] = 0
        state["sent_date"] = today
    state["sent_today"] = state.get("sent_today", 0) + 1

# ── Core scan ────────────────────────────────────────────────────────────────

async def run_scan(app: Application) -> None:
    log.info("Scan started")
    seen = clean_seen(load_seen())
    new_seen = dict(seen)
    now_iso = datetime.now().isoformat()

    try:
        all_jobs, error_sites = await asyncio.to_thread(scrape_all_sites)
    except Exception as e:
        log.error(f"Scrape failed: {e}")
        await app.bot.send_message(chat_id=CHAT_ID,
            text="⚠️ שגיאה כללית בסריקה\n🔄 ננסה בסריקה הבאה")
        return

    for site in error_sites:
        try:
            await app.bot.send_message(chat_id=CHAT_ID,
                text=f"⚠️ שגיאה בסריקה מ-{site}\n🔄 ננסה בסריקה הבאה")
        except Exception:
            pass

    state = load_state()
    found = []

    for job in all_jobs:
        h = job_hash(job)
        if h in seen:
            continue
        if keyword_match(job):
            job["_via"] = "מילות מפתח"
            found.append(job)
        else:
            if await groq_check(job):
                job["_via"] = "פרופיל AI"
                found.append(job)
        new_seen[h] = now_iso

    save_seen(new_seen)

    for job in found:
        try:
            await send_job(app, job, state)
            await asyncio.sleep(0.5)
        except Exception as e:
            log.error(f"Send failed: {e}")

    state["last_scan"] = datetime.now(ISRAEL_TZ).isoformat()
    save_state(state)

    summary = (
        f"✅ סיום סריקה\n📊 נסרקו: {len(all_jobs)} משרות\n"
        f"🎯 נמצאו: {len(found)} משרות\n⏰ סריקה הבאה: מחר 10:00"
        if found else
        f"🔍 לא נמצאו משרות חדשות היום\n⏰ סריקה הבאה: מחר 10:00"
    )
    await app.bot.send_message(chat_id=CHAT_ID, text=summary)
    log.info(f"Scan done — {len(found)} new jobs / {len(all_jobs)} total")

# ── Daily scan loop (pure asyncio, no APScheduler) ───────────────────────────

async def daily_scan_loop(app: Application) -> None:
    while True:
        now    = datetime.now(ISRAEL_TZ)
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        log.info(f"Next scan in {wait/3600:.1f}h ({target.strftime('%d/%m %H:%M')} IL)")
        await asyncio.sleep(wait)
        state = load_state()
        if not state.get("paused"):
            await run_scan(app)
        else:
            log.info("Daily scan skipped — paused")

# ── Confirmation helper ───────────────────────────────────────────────────────

def confirm_kb(yes: str, no: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ כן", callback_data=yes),
        InlineKeyboardButton("❌ לא", callback_data=no),
    ]])

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"GOT /start from {update.effective_user.id}", flush=True)
    await update.message.reply_text(
        "👋 שלום נועם!\n\n"
        "אני הבוט שלך לציד עבודה בתחום AI & Automation 🤖\n\n"
        "• סורק 9 אתרי דרושים כל יום בשעה 10:00\n"
        "• מסנן לפי מילות מפתח + בדיקת Groq AI\n"
        "• שולח רק משרות חדשות שמתאימות\n\n"
        "📋 לרשימת פקודות: /help"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 פקודות:\n\n"
        "/scan — סריקה ידנית (מקסימום פעם ביום)\n"
        "/status — סטטוס אחרון\n"
        "/clear — מחיקת משרות שמורות\n"
        "/pause — עצירת סריקות אוטומטיות\n"
        "/resume — הפעלה מחדש"
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = load_state()
    if state.get("manual_date") == date.today().isoformat():
        await update.message.reply_text(
            "⚠️ כבר בוצעה סריקה ידנית היום.\n⏰ הסריקה הבאה: מחר 10:00")
        return
    await update.message.reply_text(
        "עומד לסרוק 9 אתרים. להמשיך?",
        reply_markup=confirm_kb("yes_scan", "no_scan"))

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = load_state()
    last  = state.get("last_scan")
    last_str = datetime.fromisoformat(last).strftime("%d/%m/%Y %H:%M") if last else "טרם בוצעה"
    today = date.today().isoformat()
    sent  = state.get("sent_today", 0) if state.get("sent_date") == today else 0
    paused = state.get("paused", False)
    await update.message.reply_text(
        f"📊 סטטוס:\n\n"
        f"🔄 מצב: {'⏸ מושהה' if paused else '▶️ פעיל'}\n"
        f"🕐 סריקה אחרונה: {last_str}\n"
        f"📨 משרות שנשלחו היום: {sent}\n"
        f"💾 משרות שמורות: {len(load_seen())}\n"
        f"⏰ סריקה הבאה: {'מושהה' if paused else 'מחר 10:00'}"
    )

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    count = len(load_seen())
    await update.message.reply_text(
        f"עומד למחוק {count} משרות שמורות. להמשיך?",
        reply_markup=confirm_kb("yes_clear", "no_clear"))

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "עומד לעצור סריקות אוטומטיות. להמשיך?",
        reply_markup=confirm_kb("yes_pause", "no_pause"))

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "עומד להפעיל מחדש סריקות אוטומטיות. להמשיך?",
        reply_markup=confirm_kb("yes_resume", "no_resume"))

# ── Callback handler ──────────────────────────────────────────────────────────

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q    = update.callback_query
    await q.answer()
    data = q.data

    if data == "yes_scan":
        state = load_state()
        state["manual_date"] = date.today().isoformat()
        save_state(state)
        await q.edit_message_text("🔍 מתחיל סריקה...")
        await run_scan(context.application)

    elif data == "no_scan":
        await q.edit_message_text("❌ הסריקה בוטלה.")

    elif data == "yes_clear":
        SEEN_FILE.write_text("{}", encoding="utf-8")
        await q.edit_message_text("🗑 המשרות השמורות נמחקו.")

    elif data == "no_clear":
        await q.edit_message_text("❌ המחיקה בוטלה.")

    elif data == "yes_pause":
        state = load_state()
        state["paused"] = True
        save_state(state)
        await q.edit_message_text("⏸ סריקות אוטומטיות הושהו. /resume להפעלה מחדש.")

    elif data == "no_pause":
        await q.edit_message_text("❌ ההשהיה בוטלה.")

    elif data == "yes_resume":
        state = load_state()
        state["paused"] = False
        save_state(state)
        await q.edit_message_text("▶️ סריקות אוטומטיות הופעלו. הסריקה הבאה בשעה 10:00.")

    elif data == "no_resume":
        await q.edit_message_text("❌ ההפעלה מחדש בוטלה.")

# ── post_init: start the scheduler once the event loop is live ────────────────

async def post_init(app: Application) -> None:
    asyncio.create_task(daily_scan_loop(app))
    log.info("Daily scan loop scheduled (10:00 AM Israel time)")

# ── App setup ─────────────────────────────────────────────────────────────────

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
if not CHAT_ID:
    raise RuntimeError("TELEGRAM_CHAT_ID is not set in .env")
if not GROQ_KEY:
    log.warning("GROQ_API_KEY not set — Track 2 (AI profile check) disabled")

app = Application.builder().token(TOKEN).post_init(post_init).build()

app.add_handler(CommandHandler("start",  cmd_start))
app.add_handler(CommandHandler("help",   cmd_help))
app.add_handler(CommandHandler("scan",   cmd_scan))
app.add_handler(CommandHandler("status", cmd_status))
app.add_handler(CommandHandler("clear",  cmd_clear))
app.add_handler(CommandHandler("pause",  cmd_pause))
app.add_handler(CommandHandler("resume", cmd_resume))
app.add_handler(CallbackQueryHandler(on_button))

app.run_polling(drop_pending_updates=True)
