"""Agent วิเคราะห์ข่าวเศรษฐกิจ/หุ้นต่างประเทศ (Claude Sonnet)"""
from __future__ import annotations

import os
import logging
from typing import Any

log = logging.getLogger("agent_foreign")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 600  # เผื่อไม่ให้คำตอบภาษาไทยถูกตัดกลางคัน

DISCLAIMER = "หมายเหตุ: นี่เป็นเพียงการวิเคราะห์เบื้องต้น ไม่ใช่คำแนะนำการลงทุน"

SYSTEM_PROMPT = """คุณคือนักวิเคราะห์ข่าวเศรษฐกิจและตลาดหุ้นต่างประเทศ หน้าที่ของคุณคือสรุปข่าวที่ได้รับให้สั้นกระชับที่สุด (3-4 บรรทัด) แต่ได้ใจความครบถ้วน โดยเน้นวิเคราะห์ว่าข่าวนี้ส่งผลต่อตลาดหุ้นโลก/หุ้นกลุ่มใด และเชื่อมโยงผลกระทบมาถึงตลาดหุ้นไทยหรือนักลงทุนไทยอย่างไร (ถ้าเกี่ยวข้อง)

รูปแบบคำตอบ:
1. สรุปเนื้อข่าวสั้นๆ
2. "ผลดีต่อ:" ระบุตลาด/กลุ่มหุ้น/ภาคส่วนที่ได้ประโยชน์
3. "ผลเสียต่อ:" ระบุตลาด/กลุ่มหุ้น/ภาคส่วนที่เสียประโยชน์
4. ปิดท้ายด้วยข้อความนี้เสมอ:
   "%s"

ห้ามชี้นำให้ซื้อ/ขาย/ลงทุนใดๆ โดยเด็ดขาด

ตอบเป็นข้อความธรรมดาเท่านั้น ห้ามใช้สัญลักษณ์ Markdown ใดๆ (เช่น ** ## * _ `) ไม่ต้องทำตัวหนาหรือหัวข้อแบบ markdown""" % DISCLAIMER

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def _build_user_message(item: dict[str, Any]) -> str:
    parts = [f"หัวข้อข่าว: {item.get('title', '')}"]
    if item.get("summary"):
        parts.append(f"เนื้อหา: {item['summary']}")
    if item.get("source"):
        parts.append(f"แหล่งข่าว: {item['source']}")
    return "\n".join(parts)


def analyze(item: dict[str, Any], model: str | None = None) -> str:
    """ส่งข่าวให้ Claude วิเคราะห์ คืนข้อความสรุป (มี disclaimer ปิดท้ายเสมอ)

    model: ระบุเพื่อ override โมเดล (เช่น Opus ช่วงข่าว high-impact); None = ค่าเริ่มต้น
    """
    client = _get_client()
    resp = client.messages.create(
        model=model or MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(item)}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text").strip()
    if DISCLAIMER not in text:
        text = f"{text}\n{DISCLAIMER}"
    return text


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO)
    sample = {
        "title": "Fed signals rate cut as inflation cools to 2.4%",
        "summary": "The Federal Reserve hinted at a possible rate cut later this year.",
        "source": "investing.com/economy",
    }
    print(analyze(sample))
