#!/usr/bin/env python3
"""Audit Fantasy 5 JSON coverage without inventing results.
Run from repository root: python scripts/check_ca5.py
"""
import datetime as dt
import json
from pathlib import Path
import sys

START = dt.date(2026, 1, 1)
# Last fully elapsed California calendar date, not necessarily a published draw.
CALIFORNIA_TZ = None
try:
    from zoneinfo import ZoneInfo
    CALIFORNIA_TZ = ZoneInfo('America/Los_Angeles')
except Exception:
    pass
TODAY_CA = dt.datetime.now(CALIFORNIA_TZ).date() if CALIFORNIA_TZ else dt.datetime.now(dt.timezone.utc).date()
END = TODAY_CA - dt.timedelta(days=1)
ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'data' / 'ca5.json'
if not path.exists():
    # Allow running alongside the uploaded JSON as well.
    path = Path(__file__).resolve().parent / 'ca5.json'
if not path.exists():
    sys.exit('找不到 data/ca5.json，請把檢查程式放在專案 scripts/ 資料夾。')
rows = json.loads(path.read_text(encoding='utf-8-sig'))
if not isinstance(rows, list):
    sys.exit('JSON 應為陣列格式。')
seen = set()
invalid = []
duplicates = []
for i, r in enumerate(rows, 1):
    try:
        date = dt.date.fromisoformat(r['draw_date'])
        nums = r['numbers']
        assert isinstance(nums, list) and len(nums) == 5
        assert len(set(nums)) == 5 and all(type(n) is int and 1 <= n <= 39 for n in nums)
        assert r['special'] is None
        assert r['draw_no'] == r['draw_date']
        if date in seen:
            duplicates.append(str(date))
        seen.add(date)
    except (KeyError, ValueError, TypeError, AssertionError):
        invalid.append(i)
expected = [START + dt.timedelta(days=i) for i in range(max(0, (END - START).days + 1))]
missing = [str(day) for day in expected if day not in seen]
print('加州天天樂資料完整性檢查')
print('檢查範圍:', START, '至', END, '(加州當地已完整結束日期)')
print('檔案總筆數:', len(rows), '| 不重複日期:', len(seen))
print('缺少日期:', len(missing), '| 重複日期:', len(duplicates), '| 格式錯誤:', len(invalid))
if seen:
    print('最早資料:', min(seen), '| 最新資料:', max(seen))
if invalid:
    print('格式錯誤列:', invalid)
if duplicates:
    print('重複日期:', ', '.join(duplicates))
if missing:
    print('缺少日期列表（僅供查核，需核對是否開獎；不代表每一天必定有獎期）:')
    print('\n'.join(missing))
print('注意：本程式不下載或產生開獎號碼；缺少日期仍需由可信來源補入。')
