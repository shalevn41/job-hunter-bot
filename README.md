# 🔍 Job Hunter Bot

> 🚧 This project is currently under active development.

A Telegram bot that automatically hunts Israeli job listings using dual-track filtering — keyword matching + AI profile matching.

## ✨ Features

- 🔎 Scrapes Israeli job boards automatically
- 🤖 AI-powered matching based on personal profile
- 🏷️ Keyword-based filtering
- 📬 Sends matching jobs directly to Telegram
- 🧠 Remembers seen jobs to avoid duplicates

## 🛠️ Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core language |
| python-telegram-bot | Telegram integration |
| Groq API | AI profile matching |
| BeautifulSoup / Requests | Web scraping |
| Railway | Cloud deployment |

## 🚀 How It Works

1. Bot scrapes Israeli job boards on a schedule
2. Each listing is checked against keyword filters
3. AI compares listing to personal profile for relevance
4. Matching jobs are sent to Telegram instantly
5. Seen jobs are saved to avoid duplicate alerts

## ⚙️ Setup

1. Clone the repo
2. Create a .env file with:
TELEGRAM_BOT_TOKEN=your_token
GROQ_API_KEY=your_key
3. Install dependencies:
pip install -r requirements.txt
4. Run:
python bot.py

## 📦 Deployment

Deployed on Railway for 24/7 automated job hunting.

---

Built by Noam Shalev — AI & No-Code Automation Specialist
