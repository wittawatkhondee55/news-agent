"""ส่งสรุปข่าวเข้า Telegram ผ่าน Bot API sendMessage"""
from __future__ import annotations

import os
import re
import html
import logging

import requests

log = logging.getLogger("notify")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4096  # Telegram จำกัดความยาวข้อความต่อข้อความ
REQUEST_TIMEOUT = 20


def _config() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    return token, chat_id


def is_configured() -> bool:
    token, chat_id = _config()
    return bool(token and chat_id)


def _md_to_telegram_html(text: str) -> str:
    """แปลง Markdown ที่โมเดลอาจหลุดมา -> Telegram HTML (ตาข่ายกันพลาด)

    ทำ html.escape ก่อน แล้วค่อยแปลงสัญลักษณ์ markdown ที่เหลือ เพื่อให้ปลอดภัย
    จาก <, >, & ที่อาจอยู่ในเนื้อข่าว
    """
    text = html.escape(text)
    # **bold** หรือ __bold__ -> <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text, flags=re.S)
    # หัวข้อ markdown (#, ##, ...) ต้นบรรทัด -> ตัวหนา
    text = re.sub(r"(?m)^\s*#{1,6}\s*(.+?)\s*$", r"<b>\1</b>", text)
    # bullet '* ' หรือ '- ' ต้นบรรทัด -> •
    text = re.sub(r"(?m)^\s*[\*\-]\s+", "• ", text)
    # ลบ * หรือ _ เดี่ยวๆ ที่หลงเหลือ (italic) ออกเพื่อความสะอาด
    text = text.replace("*", "")
    return text


def format_message(item: dict, analysis: str) -> str:
    """จัดรูปข้อความเป็น HTML สำหรับ Telegram"""
    title = html.escape(item.get("title", ""))
    source = html.escape(item.get("source", ""))
    link = item.get("link", "")
    body = _md_to_telegram_html(analysis)

    lines = [f"📰 <b>{title}</b>", f"<i>({source})</i>", "", body]
    if link:
        lines.append("")
        lines.append(f'🔗 <a href="{html.escape(link)}">อ่านข่าวเต็ม</a>')
    msg = "\n".join(lines)
    if len(msg) > MAX_LEN:
        msg = msg[: MAX_LEN - 1] + "…"
    return msg


def send_telegram(text: str) -> bool:
    """ส่งข้อความ HTML เข้า Telegram — คืน True ถ้าสำเร็จ"""
    token, chat_id = _config()
    if not (token and chat_id):
        log.warning("Telegram not configured (missing token/chat_id) — skip send")
        return False
    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        ok = resp.json().get("ok", False)
        if not ok:
            log.error("Telegram API returned not-ok: %s", resp.text)
        return bool(ok)
    except Exception as exc:
        log.error("send_telegram error: %s", exc)
        return False


def notify(item: dict, analysis: str) -> bool:
    return send_telegram(format_message(item, analysis))


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO)
    demo_item = {
        "title": "ทดสอบส่งข่าวเข้า Telegram",
        "source": "prachachat.net",
        "link": "https://www.prachachat.net",
    }
    demo_analysis = "นี่คือข้อความทดสอบ\nหมายเหตุ: นี่เป็นเพียงการวิเคราะห์เบื้องต้น ไม่ใช่คำแนะนำการลงทุน"
    print("--- ตัวอย่างข้อความที่จะส่ง ---")
    print(format_message(demo_item, demo_analysis))
    print("--- ผลส่งจริง ---")
    print("configured:", is_configured())
    if is_configured():
        print("sent:", notify(demo_item, demo_analysis))
