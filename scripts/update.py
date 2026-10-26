#!/usr/bin/env python3
"""Synchronize lottery archives. Never synthesize missing draws."""
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'data'
GAMES = {'tw539': (39, 5, False), 'hk6': (49, 6, True), 'ca5': (39, 5, False)}
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/json,text/csv'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode('utf-8-sig')


def validate(game, row):
    maximum, count, has_special = GAMES[game]
    date = str(row['draw_date'])[:10]
    day = dt.date.fromisoformat(date)
    if not dt.date(2026, 1, 1) <= day <= TODAY:
        raise ValueError('draw date out of range: ' + date)
    raw = row['numbers']
    numbers = [int(x) for x in (raw if isinstance(raw, list) else re.findall(r'\d+', str(raw)))]
    special = row.get('special')
    special = int(special) if special not in (None, '') else None
    if len(numbers) != count or len(set(numbers)) != count or not all(1 <= n <= maximum for n in numbers):
        raise ValueError('invalid draw numbers: ' + str(row))
    if has_special and (special is None or special in numbers or not 1 <= special <= maximum):
        raise ValueError('invalid special number')
    if not has_special and special is not None:
        raise ValueError('unexpected special number')
    return {'draw_no': str(row['draw_no']).strip(), 'draw_date': date,
            'numbers': sorted(numbers), 'special': special}


def parse_feed(content):
    try:
        obj = json.loads(content)
        return obj['draws'] if isinstance(obj, dict) else obj
    except json.JSONDecodeError:
        return list(csv.DictReader(io.StringIO(content)))


class TextBits(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bits = []

    def handle_data(self, data):
        data = data.strip()
        if data:
            self.bits.append(data)


def ca_archive(content):
    parser = TextBits()
    parser.feed(content)
    bits = parser.bits
    rows = []
    for i, item in enumerate(bits):
        if not re.fullmatch(r'2026-\d{2}-\d{2}', item):
            continue
        near = ' '.join(bits[i + 1:i + 9])
        match = re.search(r'\b(\d{1,2})\s*[,，]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})\s*[,，]\s*(\d{1,2})\b', near)
        if match:
            rows.append({'draw_no': item, 'draw_date': item,
                         'numbers': [int(n) for n in match.groups()], 'special': None})
    return rows


def hk_archive(content):
    parser = TextBits()
    parser.feed(content)
    bits = parser.bits
    rows = []
    for i, item in enumerate(bits):
        if not re.fullmatch(r'26/\d{3}', item):
            continue
        if i + 8 >= len(bits) or not re.fullmatch(r'\d{2}/\d{2}/2026', bits[i + 1]):
            continue
        try:
            nums = [int(n) for n in bits[i + 2:i + 9]]
            day = dt.datetime.strptime(bits[i + 1], '%d/%m/%Y').date().isoformat()
            rows.append({'draw_no': item, 'draw_date': day,
                         'numbers': nums[:6], 'special': nums[6]})
        except (ValueError, IndexError):
            continue
    return rows


def recent_539(content):
    import html
    plain = html.unescape(re.sub(r'<[^>]+>', ' ', content))
    plain = re.sub(r'\s+', ' ', plain)
    pattern = r'(\d{4}/\d{1,2}/\d{1,2})\s*(?:週[一二三四五六日])?\s*(115000\d{3})\s+((?:\d{1,2}\s+){4}\d{1,2})'
    rows = []
    for match in re.finditer(pattern, plain):
        try:
            rows.append(validate('tw539', {'draw_no': match.group(2),
                        'draw_date': match.group(1).replace('/', '-'), 'numbers': match.group(3)}))
        except ValueError:
            continue
    return rows


def fetch_rows(game):
    override = os.getenv(game.upper() + '_FEED_URL', '').strip()
    if override:
        return parse_feed(fetch(override))
    if game == 'ca5':
        rows = []
        for month in range(1, TODAY.month + 1):
            url = 'https://lotterypredictor.com/california/fantasy5/results?resultsdate=2026-%02d-01' % month
            monthly = [r for r in ca_archive(fetch(url)) if int(r['draw_date'][5:7]) == month]
            if not monthly:
                raise ValueError('no Fantasy 5 results for month %02d; check page format' % month)
            print('ca5 month %02d: %d draws' % (month, len(monthly)), flush=True)
            rows.extend(monthly)
        return rows
    if game == 'hk6':
        return hk_archive(fetch('https://lottery.hk/en/mark-six/results/2026'))
    return recent_539(fetch('https://playsport539.com/lottery/539/'))


def update(game):
    path = ROOT / (game + '.json')
    existing = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    current = {r['draw_no']: validate(game, r) for r in existing}
    try:
        incoming = fetch_rows(game)
        if not incoming:
            raise ValueError('source returned no parseable results')
        additions = corrections = 0
        for row in incoming:
            new = validate(game, row)
            old = current.get(new['draw_no'])
            additions += old is None
            if old is not None and old != new:
                corrections += 1
                print('WARNING %s: conflicting record %s; keeping existing pending verification' % (game, new['draw_no']), flush=True)
                continue
            current[new['draw_no']] = new
        result = sorted(current.values(), key=lambda r: (r['draw_date'], r['draw_no']), reverse=True)
        if game == 'ca5':
            start = dt.date(2026, 1, 1)
            # California drawing happens in local Pacific time; do not require today's result yet.
            last = TODAY - dt.timedelta(days=1)
            dates = {dt.date.fromisoformat(r['draw_date']) for r in result}
            missing = [start + dt.timedelta(days=i) for i in range((last - start).days + 1)
                       if start + dt.timedelta(days=i) not in dates]
            if missing:
                print('WARNING ca5: %d dates not yet covered; first missing %s; saving available history' % (len(missing), missing[0]), flush=True)
        if result != existing:
            path.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        print('%s: %d draws, +%d new, %d corrected' % (game, len(result), additions, corrections), flush=True)
        return True
    except Exception as error:
        print('%s: sync failed (%s); existing records retained' % (game, error), file=sys.stderr, flush=True)
        if game in ('tw539', 'hk6') and existing:
            print('WARNING %s: existing %d records retained; source requires repair' % (game, len(existing)), flush=True)
            return True
        return False


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    outcomes = {game: update(game) for game in GAMES}
    if not all(outcomes.values()):
        print('ERROR: one or more lottery sources failed; check log.', file=sys.stderr)
        sys.exit(1)
