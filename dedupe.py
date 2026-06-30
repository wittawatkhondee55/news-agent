"""ป้องกันข่าวซ้ำด้วย hash ของหัวข้อข่าว เก็บใน processed_news.json"""
from __future__ import annotations

import os
import json
import hashlib
import logging
from typing import Any, Iterable

log = logging.getLogger("dedupe")

DEFAULT_STORE = os.path.join(os.path.dirname(__file__), "processed_news.json")

# จำนวน hash สูงสุดที่เก็บ (กันไฟล์โตไม่จำกัด) — เก่าสุดจะถูกตัดทิ้งก่อน
MAX_HASHES = 5000


def get_news_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8")).hexdigest()


def load_processed(path: str = DEFAULT_STORE) -> list[str]:
    """คืน list ของ hash ที่ประมวลผลแล้ว (เรียงเก่า->ใหม่)"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hashes = data.get("hashes", []) if isinstance(data, dict) else data
        return list(hashes) if isinstance(hashes, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("load_processed error (%s) -> treating as empty", exc)
        return []


def save_processed(hashes: Iterable[str], path: str = DEFAULT_STORE) -> None:
    """บันทึก hash โดยตัดให้เหลือไม่เกิน MAX_HASHES ตัวล่าสุด"""
    trimmed = list(hashes)[-MAX_HASHES:]
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"hashes": trimmed}, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)  # atomic เพื่อกันไฟล์พังถ้าโดนขัดจังหวะ


def filter_new(
    items: list[dict[str, Any]], path: str = DEFAULT_STORE
) -> list[dict[str, Any]]:
    """คืนเฉพาะข่าวที่ยังไม่เคยประมวลผล และฝัง '_hash' ลงในแต่ละ item"""
    seen = set(load_processed(path))
    fresh: list[dict[str, Any]] = []
    seen_this_run: set[str] = set()
    for it in items:
        h = get_news_hash(it["title"])
        if h in seen or h in seen_this_run:
            continue
        it["_hash"] = h
        seen_this_run.add(h)
        fresh.append(it)
    log.info("filter_new: %d in -> %d new", len(items), len(fresh))
    return fresh


def mark_processed(items: list[dict[str, Any]], path: str = DEFAULT_STORE) -> None:
    """เพิ่ม hash ของข่าวที่ส่งสำเร็จแล้วลง store"""
    existing = load_processed(path)
    new_hashes = [it["_hash"] for it in items if it.get("_hash")]
    save_processed(existing + new_hashes, path)
    log.info("mark_processed: +%d hashes (total kept <= %d)", len(new_hashes), MAX_HASHES)


if __name__ == "__main__":
    demo = [
        {"title": "ข่าว A"},
        {"title": "ข่าว B"},
        {"title": "ข่าว A"},  # ซ้ำในรอบเดียวกัน
    ]
    test_path = os.path.join(os.path.dirname(__file__), "_dedupe_test.json")
    if os.path.exists(test_path):
        os.remove(test_path)
    first = filter_new(demo, test_path)
    print("รอบแรก new:", [d["title"] for d in first])
    mark_processed(first, test_path)
    second = filter_new(demo, test_path)
    print("รอบสอง new:", [d["title"] for d in second])  # ควรว่าง
    os.remove(test_path)
