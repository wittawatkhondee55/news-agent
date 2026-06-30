"""แยกประเภทข่าวตามแหล่งที่มา (ไม่เรียก AI — ประหยัด token)"""
from __future__ import annotations

# ปรับให้ตรงกับชื่อแหล่งจริงใน fetch_news.RSS_SOURCES
THAI_SOURCES = ["prachachat", "set.or.th"]
FOREIGN_SOURCES = ["investing.com", "forexfactory", "tradingeconomics"]

AGENT_THAI = "agent_thai"
AGENT_FOREIGN = "agent_foreign"
UNKNOWN = "unknown"


def route(source_name: str) -> str:
    """คืน 'agent_thai' / 'agent_foreign' / 'unknown' ตามชื่อแหล่ง"""
    name = (source_name or "").lower()
    if any(s in name for s in THAI_SOURCES):
        return AGENT_THAI
    if any(s in name for s in FOREIGN_SOURCES):
        return AGENT_FOREIGN
    return UNKNOWN


if __name__ == "__main__":
    samples = [
        "prachachat.net",
        "set.or.th",
        "investing.com/stock",
        "investing.com/economy",
        "forexfactory",
        "somethingelse.com",
    ]
    for s in samples:
        print(f"{s:30s} -> {route(s)}")
