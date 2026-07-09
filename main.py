"""Pipeline หลัก: fetch -> dedupe -> route -> analyze -> notify -> mark

รันแบบ manual:    python main.py
รันแบบ dry-run:   python main.py --dry-run   (ไม่เรียก Claude/Telegram จริง)

โหมด dry-run จะถูกเปิดอัตโนมัติถ้าไม่มี ANTHROPIC_API_KEY เพื่อให้ทดสอบ
fetch/router/dedupe ได้โดยไม่ต้องมีคีย์
"""
from __future__ import annotations

import os
import sys
import time
import logging

import fetch_news
import router
import dedupe
import notify
import events
import agent_thai
import agent_foreign

# เพดานกันการวิ่งเสียการควบคุม ไม่ใช่การจำกัดปริมาณข่าวจริง (ใช้ Haiku ต้นทุนต่ำ
# จึงไม่จำกัดปริมาณตามที่ต้องการ) — แหล่งจริงรวมกันไม่เกิน ~150 ข่าว/รอบ จึงไม่มี
# ทางแตะเพดานนี้ในทางปฏิบัติ ใช้ `or "300"` กัน env ถูกตั้งเป็นค่าว่าง
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN") or "300")

# เว้นจังหวะระหว่างส่งแต่ละข้อความเข้า Telegram กันโดน rate-limit (429) เมื่อ
# ปริมาณข่าวต่อรอบพุ่งสูง (เช่นวันที่ SET มีข่าวเยอะ) — Telegram แนะนำไม่เกิน
# ~1 ข้อความ/วินาทีต่อแชตเดียวกัน
TELEGRAM_SEND_INTERVAL_SEC = 1.1

# โมเดลที่ใช้ช่วงข่าว high-impact (ตาม spec: สลับไป Opus เฉพาะข่าวสำคัญ)
HIGH_IMPACT_MODEL = os.environ.get("HIGH_IMPACT_MODEL", "claude-opus-4-8")

AGENTS = {
    router.AGENT_THAI: agent_thai.analyze,
    router.AGENT_FOREIGN: agent_foreign.analyze,
}

log = logging.getLogger("main")


def _setup_logging() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run(dry_run: bool = False) -> int:
    """รัน pipeline หนึ่งรอบ คืนจำนวนข่าวที่ส่งสำเร็จ"""
    if not os.environ.get("ANTHROPIC_API_KEY") and not dry_run:
        log.warning("ไม่พบ ANTHROPIC_API_KEY — สลับเป็น dry-run อัตโนมัติ")
        dry_run = True

    # 1) fetch
    items = fetch_news.fetch_all()

    # 2) dedupe — เอาเฉพาะข่าวใหม่
    fresh = dedupe.filter_new(items)
    if not fresh:
        log.info("ไม่มีข่าวใหม่ — จบรอบ")
        return 0

    fresh = fresh[:MAX_PER_RUN]

    # ตรวจช่วงข่าวสำคัญ -> ถ้าใช่ ใช้ Opus เพื่อคุณภาพสูงสุด (ตาม spec ข้อ 4)
    hot = events.active_event()
    model_override = HIGH_IMPACT_MODEL if (hot and hot.get("impact") == "high") else None
    if hot:
        log.info("อยู่ในช่วงข่าวสำคัญ: %s -> ใช้โมเดล %s",
                 hot.get("label"), model_override or "default")
    log.info("จะประมวลผล %d ข่าว (dry_run=%s)", len(fresh), dry_run)

    sent_items = []
    for it in fresh:
        # 3) route
        target = router.route(it["source"])
        agent_fn = AGENTS.get(target)
        if agent_fn is None:
            log.info("ข้าม (unknown source): %s", it["source"])
            continue

        # 4) analyze
        try:
            if dry_run:
                tag = model_override or "default"
                analysis = (
                    f"[DRY-RUN | {target} | {tag}] วิเคราะห์ข่าว: {it['title']}\n"
                    f"{agent_thai.DISCLAIMER}"
                )
            else:
                analysis = agent_fn(it, model=model_override)
        except Exception as exc:
            log.error("วิเคราะห์ล้มเหลว (%s): %s", it["title"][:40], exc)
            continue

        # 5) notify
        if dry_run or not notify.is_configured():
            print("\n" + "=" * 60)
            print(notify.format_message(it, analysis))
            ok = True
        else:
            ok = notify.notify(it, analysis)
            time.sleep(TELEGRAM_SEND_INTERVAL_SEC)  # เว้นจังหวะกัน Telegram 429

        if ok:
            sent_items.append(it)

    # 6) mark processed — เฉพาะข่าวที่ส่งสำเร็จ (กันข่าวหายถ้า notify ล้ม)
    #    ในโหมด dry-run ไม่บันทึก เพื่อให้ทดสอบซ้ำได้
    if sent_items and not dry_run:
        dedupe.mark_processed(sent_items)

    log.info("เสร็จรอบ: ส่งสำเร็จ %d/%d ข่าว", len(sent_items), len(fresh))
    return len(sent_items)


if __name__ == "__main__":
    _setup_logging()
    dry = "--dry-run" in sys.argv
    count = run(dry_run=dry)
    print(f"\n>>> ส่งข่าวสำเร็จ {count} ข่าว")
