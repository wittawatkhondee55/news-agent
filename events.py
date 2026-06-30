"""ปฏิทินเหตุการณ์สำคัญ + ตรรกะตรวจ "ช่วงข่าวสำคัญ" (smart polling)

ใช้รู้ว่าตอนนี้อยู่ในช่วง ±N นาทีรอบเหตุการณ์ high-impact หรือไม่ เพื่อ:
  1) ให้ workflow เร่งความถี่ดึงข่าว (run-fast.yml เรียก is_window ผ่าน exit code)
  2) ให้ main.py สลับไปใช้โมเดล Opus เฉพาะช่วงนั้น (คุณภาพสูงกับข่าวสำคัญ)

ใช้ stdlib ล้วน (datetime, json) — ไม่มี dependency เพื่อให้ gate ใน CI รันเร็ว
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

log = logging.getLogger("events")

DEFAULT_STORE = os.path.join(os.path.dirname(__file__), "events.json")
DEFAULT_WINDOW_MIN = 10


def _parse_dt(value: str) -> datetime | None:
    try:
        # รองรับทั้ง '...Z' และ offset '+07:00'
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def load_events(path: str = DEFAULT_STORE) -> tuple[list[dict[str, Any]], int]:
    """คืน (events, window_minutes) — events ว่างถ้าไฟล์ไม่มี/พัง"""
    if not os.path.exists(path):
        return [], DEFAULT_WINDOW_MIN
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("load_events error (%s) -> empty", exc)
        return [], DEFAULT_WINDOW_MIN
    window = int(data.get("window_minutes", DEFAULT_WINDOW_MIN))
    return list(data.get("events", [])), window


def active_event(
    now: datetime | None = None, path: str = DEFAULT_STORE
) -> dict[str, Any] | None:
    """คืน event ที่ตอนนี้อยู่ในช่วง ±window นาที (impact สูงสุดก่อน) หรือ None"""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    events, window = load_events(path)
    delta = timedelta(minutes=window)
    hits = []
    for ev in events:
        dt = _parse_dt(ev.get("datetime_utc", ""))
        if dt and abs(now - dt) <= delta:
            hits.append(ev)
    if not hits:
        return None
    # ให้ความสำคัญ high ก่อน
    hits.sort(key=lambda e: 0 if e.get("impact") == "high" else 1)
    return hits[0]


def is_high_impact_window(
    now: datetime | None = None, path: str = DEFAULT_STORE
) -> bool:
    ev = active_event(now, path)
    return bool(ev and ev.get("impact") == "high")


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO)

    ev = active_event()
    print("ตอนนี้ (UTC):", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print("ช่วงข่าวสำคัญ:", "ใช่" if is_high_impact_window() else "ไม่")
    print("event ที่ active:", ev["label"] if ev else "-")

    # ทดสอบด้วยเวลาจำลองให้ตรงกับ event แรกใน events.json
    evs, win = load_events()
    if evs:
        target = _parse_dt(evs[0]["datetime_utc"])
        print(f"\n[จำลอง] ที่เวลา {evs[0]['datetime_utc']} (±{win} นาที):")
        print("  in_window:", is_high_impact_window(target))
        print("  +5 นาที :", is_high_impact_window(target + timedelta(minutes=5)))
        print("  +20 นาที:", is_high_impact_window(target + timedelta(minutes=20)))
