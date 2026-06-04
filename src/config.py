import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [
    cid.strip() for cid in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if cid.strip()
]
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

WATCHLIST = {
    "반도체": {
        "005930": "삼성전자",
        "000660": "SK하이닉스",
        "042700": "한미반도체",
        "058470": "리노공업",
    },
    "에너지": {
        "015760": "한국전력",
        "034020": "두산에너빌리티",
        "267260": "HD현대일렉트릭",
        "009830": "한화솔루션",
    },
    "배터리": {
        "373220": "LG에너지솔루션",
        "006400": "삼성SDI",
        "247540": "에코프로비엠",
        "086520": "에코프로",
    },
    "우주항공": {
        "012450": "한화에어로스페이스",
        "047810": "한국항공우주",
        "189300": "인텔리안테크",
        "274090": "켄코아에어로스페이스",
        "211270": "AP위성",
    },
}

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
