"""Agent วิเคราะห์ข่าวหุ้น/เศรษฐกิจไทย (Claude Sonnet)"""
from __future__ import annotations

import os
import logging
from typing import Any

log = logging.getLogger("agent_thai")

# ค่าเริ่มต้นตาม spec: Claude Sonnet (สมดุลคุณภาพ/ต้นทุน) — เปลี่ยนได้ผ่าน env
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 600  # เผื่อไม่ให้คำตอบภาษาไทยถูกตัดกลางคัน

DISCLAIMER = "หมายเหตุ: นี่เป็นเพียงการวิเคราะห์เบื้องต้น ไม่ใช่คำแนะนำการลงทุน"

SYSTEM_PROMPT = """คุณคือนักวิเคราะห์ข่าวหุ้นและเศรษฐกิจไทย หน้าที่ของคุณคือสรุปข่าวที่ได้รับให้สั้นกระชับที่สุด (3-4 บรรทัด) แต่ได้ใจความครบถ้วน โดยเน้นวิเคราะห์ว่าข่าวนี้ส่งผลต่อหุ้นตัวใด กลุ่มอุตสาหกรรมใด หรือภาพรวมตลาดหุ้นไทยอย่างไร

รูปแบบคำตอบ:
1. สรุปเนื้อข่าวสั้นๆ
2. "ผลดีต่อ:" ระบุชื่อหุ้น/กลุ่มอุตสาหกรรม/ภาคส่วนที่ได้ประโยชน์ (ถ้าระบุได้)
3. "ผลเสียต่อ:" ระบุชื่อหุ้น/กลุ่มอุตสาหกรรม/ภาคส่วนที่เสียประโยชน์ (ถ้าระบุได้)
4. ปิดท้ายด้วยข้อความนี้เสมอ:
   "%s"

ห้ามชี้นำให้ซื้อ/ขาย/ลงทุนหุ้นใดๆ โดยเด็ดขาด
ถ้าข่าวไม่มีผลกระทบชัดเจนต่อหุ้นตัวใดเป็นการเฉพาะ ให้วิเคราะห์ในระดับภาพรวมตลาด (SET Index) หรือกลุ่มอุตสาหกรรมที่เกี่ยวข้องแทน

ตอบเป็นข้อความธรรมดาเท่านั้น ห้ามใช้สัญลักษณ์ Markdown ใดๆ (เช่น ** ## * _ `) ไม่ต้องทำตัวหนาหรือหัวข้อแบบ markdown""" % DISCLAIMER

# client ถูกสร้างแบบ lazy ครั้งเดียว เพื่อไม่ต้องมีคีย์ตอน import
_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # import แบบ lazy

        _client = anthropic.Anthropic()  # อ่าน ANTHROPIC_API_KEY จาก env
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
    # กันกรณีโมเดลลืมใส่ disclaimer
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
        "title": "ธปท. คงอัตราดอกเบี้ยนโยบายที่ 2.00% ตามคาด",
        "summary": "คณะกรรมการนโยบายการเงินมีมติคงอัตราดอกเบี้ย ท่ามกลางเงินเฟ้อที่ชะลอตัว",
        "source": "prachachat.net",
    }
    print(analyze(sample))
