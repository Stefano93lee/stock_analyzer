import logging
import time

import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"
MAX_MSG_LEN = 4000
MAX_RETRIES = 3
RETRY_DELAY = 5


def _call(method: str, retries: int = MAX_RETRIES, **kwargs) -> dict:
    url = f"{API_BASE.format(token=TELEGRAM_BOT_TOKEN)}/{method}"

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, **kwargs, timeout=30)
            result = resp.json()
            if not result.get("ok"):
                logger.error("Telegram API error: %s", result)
            return result
        except requests.exceptions.ConnectionError as e:
            logger.warning(
                "Telegram connection failed (attempt %d/%d): %s", attempt, retries, e
            )
            if attempt < retries:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.Timeout:
            logger.warning("Telegram timeout (attempt %d/%d)", attempt, retries)
            if attempt < retries:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error("Telegram unexpected error: %s", e)
            return {"ok": False, "description": str(e)}

    logger.error(
        "Telegram send failed after %d attempts. "
        "Check: 1) TELEGRAM_BOT_TOKEN is correct, "
        "2) api.telegram.org is not blocked by firewall/VPN, "
        "3) Network connection is stable",
        retries,
    )
    return {"ok": False, "description": "Connection failed after retries"}


def _send_message_single(text: str, chat_id: str) -> bool:
    chunks = []
    remaining = text
    while len(remaining) > MAX_MSG_LEN:
        split_at = remaining.rfind("\n", 0, MAX_MSG_LEN)
        if split_at == -1:
            split_at = MAX_MSG_LEN
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    chunks.append(remaining)

    success = True
    for chunk in chunks:
        result = _call(
            "sendMessage",
            data={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
        )
        if not result.get("ok"):
            success = False
    return success


def _send_document_single(file_path: str, chat_id: str, caption: str = "") -> bool:
    with open(file_path, "rb") as f:
        result = _call(
            "sendDocument",
            data={"chat_id": chat_id, "caption": caption[:1024]},
            files={"document": f},
        )
    return result.get("ok", False)


def send_message(text: str, chat_id: str | None = None) -> bool:
    targets = [chat_id] if chat_id else TELEGRAM_CHAT_IDS
    if not TELEGRAM_BOT_TOKEN or not targets:
        logger.error("Telegram credentials not configured")
        return False

    all_ok = True
    for cid in targets:
        ok = _send_message_single(text, cid)
        if ok:
            logger.info("Message sent to chat_id=%s", cid)
        else:
            logger.error("Message failed for chat_id=%s", cid)
            all_ok = False
    return all_ok


def send_document(file_path: str, caption: str = "", chat_id: str | None = None) -> bool:
    targets = [chat_id] if chat_id else TELEGRAM_CHAT_IDS
    if not TELEGRAM_BOT_TOKEN or not targets:
        logger.error("Telegram credentials not configured")
        return False

    all_ok = True
    for cid in targets:
        ok = _send_document_single(file_path, cid, caption)
        if ok:
            logger.info("Document sent to chat_id=%s", cid)
        else:
            logger.error("Document failed for chat_id=%s", cid)
            all_ok = False
    return all_ok


def get_chat_id() -> None:
    """Telegram Bot의 chat_id를 확인하는 유틸리티 함수.
    봇에 먼저 메시지를 보낸 후 이 함수를 실행하세요."""
    result = _call("getUpdates", retries=1, data={"limit": 10})
    if result.get("ok") and result.get("result"):
        seen = set()
        for update in result["result"]:
            msg = update.get("message", {})
            chat = msg.get("chat", {})
            cid = chat.get("id")
            if cid and cid not in seen:
                seen.add(cid)
                chat_type = chat.get("type", "")
                name = chat.get("title") or f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip()
                print(f"Chat ID: {cid}  |  Type: {chat_type}  |  Name: {name}")
        print(f"\nFound {len(seen)} chat(s). Add to .env:")
        print(f"TELEGRAM_CHAT_ID={','.join(str(c) for c in seen)}")
    else:
        print("No messages found. Send a message to the bot first.")
        if not result.get("ok"):
            print(f"Error: {result.get('description', 'Connection failed')}")
