"""ดึงข่าวจาก RSS และ scraper ทุกแหล่ง

แหล่งที่ตรวจสอบแล้วว่าใช้งานได้จริง (ณ มิ.ย. 2026):
  - ประชาชาติธุรกิจ (RSS)        -> ข่าวหุ้น/เศรษฐกิจไทย
  - Investing.com TH (RSS)       -> ข่าวหุ้น/เศรษฐกิจต่างประเทศ
แหล่งเสริม (best-effort, ข้ามได้ถ้าล้มเหลว ไม่ทำให้ pipeline พัง):
  - SET (web scraping)           -> ข่าวบริษัทจดทะเบียนโดยตรง

ทุกฟังก์ชันคืน list ของ dict รูปแบบเดียวกัน:
  {"source", "title", "summary", "link", "published"}
"""
from __future__ import annotations

import time
import logging
from typing import Any

import requests
import feedparser
from bs4 import BeautifulSoup

log = logging.getLogger("fetch")

# User-Agent แบบ browser จริง — บางแหล่ง (เช่น Investing.com, SET) บล็อก UA ของ
# feedparser/requests เริ่มต้น
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20

# แหล่ง RSS — ตรวจสอบแล้วว่า live
RSS_SOURCES: list[dict[str, str]] = [
    {
        "name": "prachachat.net",
        "url": "https://www.prachachat.net/finance/feed",
    },
    {
        "name": "investing.com/stock",
        "url": "https://th.investing.com/rss/news_25.rss",
    },
    {
        "name": "investing.com/economy",
        "url": "https://th.investing.com/rss/news_14.rss",
    },
]

# เพดานกันการวิ่งเสียการควบคุม (เช่น feed เพี้ยนแล้วยัดมาเป็นพัน) ไม่ใช่การจำกัด
# ปริมาณข่าวจริง — แหล่งจริงของเรา (prachachat ~30, investing ~10, SET ~40-90/วัน)
# ยังไม่มีทางแตะเพดานนี้ จึงเท่ากับ "ไม่จำกัด" ในทางปฏิบัติ
MAX_ITEMS_PER_SOURCE = 300


def _http_get(url: str) -> bytes:
    """ดึง raw bytes พร้อม browser header — ใช้ร่วมกับทั้ง RSS และ scraper"""
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


# session สำหรับ SET — เก็บ cookie จาก warm-up ไว้ใช้ซ้ำ (สร้าง lazy ครั้งเดียว)
_set_session: requests.Session | None = None
SET_NEWS_PAGE = "https://www.set.or.th/th/market/news-and-alert/news"
SET_NEWS_API = "https://www.set.or.th/api/set/news/search?lang=th&securityType=S&limit=40"


def _get_set_session() -> requests.Session:
    """คืน session ที่ warm-up แล้ว (มี Incapsula cookie) เพื่อให้ API ไม่คืน 403

    หน้า SET มี bot-protection (Incapsula) ที่บล็อก request ไม่มี cookie ดังนั้น
    ต้องโหลดหน้าเว็บปกติก่อนหนึ่งครั้งเพื่อรับ cookie แล้วค่อยเรียก API
    """
    global _set_session
    if _set_session is not None:
        return _set_session
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "th,en;q=0.9",
            "Referer": SET_NEWS_PAGE,
        }
    )
    sess.get(SET_NEWS_PAGE, timeout=REQUEST_TIMEOUT)  # warm-up เก็บ cookie
    _set_session = sess
    return sess


def _clean(text: str | None) -> str:
    if not text:
        return ""
    # ลอก HTML tag ที่อาจติดมาใน summary ของ RSS บางเจ้า
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def fetch_rss(name: str, url: str) -> list[dict[str, Any]]:
    """ดึงข่าวจาก RSS หนึ่งแหล่ง — คืน list ว่างถ้าล้มเหลว (ไม่ throw)"""
    try:
        raw = _http_get(url)
    except Exception as exc:  # network / HTTP error
        log.warning("fetch_rss(%s) HTTP error: %s", name, exc)
        return []

    parsed = feedparser.parse(raw)
    if parsed.bozo and not parsed.entries:
        log.warning("fetch_rss(%s) parse error: %s", name, parsed.bozo_exception)
        return []

    items: list[dict[str, Any]] = []
    for entry in parsed.entries[:MAX_ITEMS_PER_SOURCE]:
        title = _clean(entry.get("title"))
        if not title:
            continue
        items.append(
            {
                "source": name,
                "title": title,
                "summary": _clean(entry.get("summary") or entry.get("description")),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            }
        )
    log.info("fetch_rss(%s) -> %d items", name, len(items))
    return items


# หัวข้อข่าว SET ที่เป็น filing รายงาน/ธุรการตามรอบ ไม่มีนัยสำคัญต่อราคาหุ้น —
# ตรวจสอบจากตัวอย่างจริง (ก.ค. 2569) พบว่าราว 3 ใน 4 ของข่าว SET ต่อวันเป็น
# ประเภทนี้ (SEC สรุปฟอร์มรายวัน, TSD รับจดทะเบียน DW, รายงานความคืบหน้าตามรอบ)
SET_NOISE_PATTERNS = [
    "การรับเป็นนายทะเบียนหลักทรัพย์",  # TSD แจ้งรับจดทะเบียน DW/ตราสารอนุพันธ์ (ธุรการล้วน)
    "SEC News :",                       # SEC สรุปแบบฟอร์มรายวัน (แบบ 59/246-2 ฯลฯ)
    "รายงานการใช้เงินเพิ่มทุน",         # รายงานความคืบหน้าใช้เงินเพิ่มทุนตามกำหนด (ธุรการ)
    "แบบรายงานผลการซื้อหุ้นคืน",       # รายงานผลซื้อหุ้นคืนที่ทำต่อเนื่อง (ไม่ใช่ประกาศโครงการใหม่)
    "แบบรายงานผลการใช้สิทธิ",          # รายงานผลใช้สิทธิ warrant/แปลงสภาพตามรอบ (ธุรการ)
]


def _is_set_noise(headline: str) -> bool:
    return any(p in headline for p in SET_NOISE_PATTERNS)


def fetch_set_news() -> list[dict[str, Any]]:
    """ดึงข่าวบริษัทจดทะเบียนจากหน้า SET (best-effort)

    หน้า SET เป็น JS-rendered + เนื้อข่าวโหลดผ่าน internal JSON API ที่มี Incapsula
    bot-protection ดังนั้นต้อง warm-up เก็บ cookie ก่อน (ดู _get_set_session).
    ถ้า SET เปลี่ยนโครงสร้าง/บล็อก -> คืน list ว่าง เพื่อไม่ให้ pipeline ทั้งหมดพัง
    (ตาม spec: แหล่งนี้ "เปราะกว่า RSS")
    """
    try:
        sess = _get_set_session()
        resp = sess.get(SET_NEWS_API, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("fetch_set_news skipped (best-effort): %s", exc)
        return []

    # โครงสร้าง response ของ SET อาจเป็น {"newsInfoList": [...]} หรือ list ตรงๆ
    rows = data.get("newsInfoList") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        log.warning("fetch_set_news: unexpected payload shape; skipping")
        return []

    items: list[dict[str, Any]] = []
    noise_count = 0
    for row in rows[:MAX_ITEMS_PER_SOURCE]:
        if not isinstance(row, dict):
            continue
        title = _clean(row.get("headline") or row.get("name"))
        if not title:
            continue
        if _is_set_noise(title):
            noise_count += 1
            continue
        symbol = row.get("symbol", "")
        items.append(
            {
                "source": "set.or.th",
                "title": f"[{symbol}] {title}" if symbol else title,
                "summary": _clean(row.get("headline")),
                "link": row.get("url", "https://www.set.or.th"),
                "published": row.get("datetime", ""),
            }
        )
    log.info("fetch_set_news -> %d items (กรองข่าวธุรการออก %d)", len(items), noise_count)
    return items


def fetch_all() -> list[dict[str, Any]]:
    """ดึงทุกแหล่งรวมกัน — แต่ละแหล่งล้มเหลวได้โดยไม่กระทบแหล่งอื่น"""
    all_items: list[dict[str, Any]] = []
    for src in RSS_SOURCES:
        all_items.extend(fetch_rss(src["name"], src["url"]))
        time.sleep(0.5)  # สุภาพกับ server

    # แหล่งเสริม — เปิดใช้ได้ แต่ปัจจุบัน SET API คืน 403 บ่อย จึงเป็น best-effort
    all_items.extend(fetch_set_news())

    log.info("fetch_all -> %d items total", len(all_items))
    return all_items


if __name__ == "__main__":
    import sys

    # Windows console เริ่มต้นเป็น cp1252 พิมพ์ภาษาไทยไม่ได้ -> บังคับ UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    items = fetch_all()
    print(f"\n=== ดึงได้ {len(items)} ข่าว ===\n")
    for it in items[:10]:
        print(f"[{it['source']}] {it['title']}")
        print(f"    {it['link']}")
