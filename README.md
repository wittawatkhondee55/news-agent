# news-agent — AI วิเคราะห์ข่าวเศรษฐกิจ/หุ้น → Telegram

ดึงข่าวหุ้น/เศรษฐกิจไทย+ต่างประเทศ → แยกประเภท → ให้ Claude Sonnet วิเคราะห์ผลกระทบต่อหุ้น/กลุ่ม → ส่งเข้า Telegram พร้อม disclaimer

## Pipeline

```
fetch_news → dedupe → router → agent_thai / agent_foreign → notify (Telegram)
```

## แหล่งข่าว (ตรวจสอบแล้วว่า live ณ มิ.ย. 2026)

| แหล่ง | ประเภท | ประเภทข่าว |
|---|---|---|
| `prachachat.net/finance/feed` | RSS | ไทย |
| `th.investing.com/rss/news_25.rss` | RSS | ต่างประเทศ (หุ้น) |
| `th.investing.com/rss/news_14.rss` | RSS | ต่างประเทศ (เศรษฐกิจ) |
| SET (`set.or.th`) | API + cookie warm-up | ไทย — ข่าวบริษัทจดทะเบียนโดยตรง (มี symbol) |

> SET API มี Incapsula bot-protection — โค้ดแก้ด้วยการ warm-up โหลดหน้าเว็บก่อนเก็บ cookie แล้วค่อยเรียก API ถ้า SET เปลี่ยนโครงสร้างในอนาคต ฟังก์ชันจะ fallback คืน list ว่างโดยไม่ทำให้ pipeline พัง

## Smart polling (ช่วงข่าวสำคัญ)

- `events.json` เก็บเหตุการณ์ high-impact (Fed/กนง./CPI) เป็นเวลา UTC
- ช่วง ±10 นาทีรอบเหตุการณ์: `run-fast.yml` เร่งดึงข่าวเป็นทุก 5 นาที และ `main.py` สลับไปใช้ **Opus** อัตโนมัติเพื่อคุณภาพสูงสุด นอกช่วงนั้น gate job จบทันที (ประหยัด Actions minutes)
- อัปเดตปฏิทินเองได้ที่ `events.json`

## ติดตั้ง & รัน local

```bash
pip install -r requirements.txt

# ทดสอบโดยไม่ต้องมีคีย์ (fetch จริง + วิเคราะห์/ส่งแบบจำลอง):
python main.py --dry-run

# รันจริง — ตั้ง env ก่อน (ดู .env.example):
#   ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
python main.py
```

ทดสอบทีละโมดูล: `python fetch_news.py` · `python router.py` · `python dedupe.py` · `python notify.py`

## รันอัตโนมัติ (GitHub Actions)

`.github/workflows/run.yml` ตั้ง schedule ทุก 30 นาที — ใส่ค่าใน **Settings → Secrets and variables → Actions**:

- Secrets: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- (ไม่บังคับ) Variable: `CLAUDE_MODEL`

workflow จะ commit `processed_news.json` กลับเพื่อจำว่าข่าวไหนส่งไปแล้ว

## หมายเหตุ

- ระบบนี้เป็นเพียงการสรุป+วิเคราะห์เบื้องต้น **ไม่ใช่คำแนะนำการลงทุน**
- ปฏิทินเศรษฐกิจ (Forex Factory/Trading Economics) ยังไม่รวมใน MVP — Forex Factory บล็อกบอท (403), Trading Economics free จำกัดประเทศ
