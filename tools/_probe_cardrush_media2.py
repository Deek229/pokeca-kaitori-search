"""Probe cardrush.media pagination and SV9 search."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shop_matching import pick_best_match

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'ja,en;q=0.9',
}
s = requests.Session()
s.headers.update(UA)

SV9 = [
    ('sv9_033', 'リーリエのピッピex', '033'),
    ('sv9_001', 'ナゾノクサ', '001'),
    ('sv9_050', 'ピカチュウex', '050'),
    ('sv9_100', 'リーリエの決心', '100'),
    ('sv9_115', 'ナンジャモ', '115'),
    ('sv9_120', 'ボスの指令', '120'),
    ('sv9_125', 'スグリ', '125'),
    ('sv9_130', 'ゼイユ', '130'),
]


def fetch_page(query: dict | None = None) -> dict:
    base = 'https://cardrush.media/pokemon/buying_prices'
    if query:
        url = base + '?' + urlencode(query)
    else:
        url = base
    r = s.get(url, timeout=60)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', r.text)
    if not m:
        return {}
    return json.loads(m.group(1)).get('props', {}).get('pageProps', {})


props = fetch_page()
print('lastPage:', props.get('lastPage'))
print('updatedAt:', props.get('updatedAt'))
print('defaultQuery:', json.dumps(props.get('defaultQuery', {}), ensure_ascii=False)[:300])

# Search SV9 via query string
for q in [
    {'pack_code': 'SV9'},
    {'name': 'リーリエ'},
    {'model_number': '033'},
    {'pack_code': 'SV9', 'page': '1'},
]:
    p = fetch_page(q)
    bp = p.get('buyingPrices') or []
    print(f'\nquery={q} -> {len(bp)} items, lastPage={p.get("lastPage")}')
    for item in bp[:3]:
        print(
            f'  {item.get("name")} {item.get("model_number")} '
            f'pack={item.get("pack_code")} amount={item.get("amount")}'
        )
    sv9_items = [i for i in bp if 'sv9' in str(i.get('pack_code', '')).lower()
                 or '033/100' in str(i.get('model_number', ''))]
    print(f'  sv9-related in page: {len(sv9_items)}')

# Try internal JSON API patterns from Next.js
print('\n=== JSON API guesses ===')
for url in [
    'https://cardrush.media/pokemon/buying_prices?pack_code=SV9&limit=100&page=1',
    'https://cardrush.media/_next/data/build-id/pokemon/buying_prices.json',
]:
    r = s.get(url, timeout=30, headers={**UA, 'Accept': 'application/json'})
    print(url[:80], r.status_code, r.text[:200])

# Paginate first 3 pages, collect SV9
all_sv9 = []
for page in range(1, 4):
    p = fetch_page({'page': str(page), 'limit': '100'})
    bp = p.get('buyingPrices') or []
    for item in bp:
        mn = str(item.get('model_number', ''))
        pc = str(item.get('pack_code', ''))
        if 'sv9' in pc.lower() or '/100' in mn:
            all_sv9.append(item)
    print(f'page {page}: {len(bp)} items, cumulative sv9-ish: {len(all_sv9)}')

print('\nSV9-ish samples:')
for item in all_sv9[:10]:
    print(f'  {item.get("name")} ({item.get("model_number")}) pack={item.get("pack_code")} amount={item.get("amount")}')

# Match test on collected SV9 items
entries = [
    {
        'title': f'{i.get("name")}({i.get("model_number")}){i.get("pack_code", "")}',
        'price_yen': int(i.get('amount') or 0),
    }
    for i in all_sv9
]
found = 0
for cid, name, lid in SV9:
    m = pick_best_match(entries, card_name=name, local_id=lid, set_tcgdex_id='SV9', min_score=70)
    if m:
        found += 1
        print(f'MATCH {cid}: {m["price_yen"]} — {m["title"][:70]}')
print(f'\nSV9 match from pages 1-3: {found}/{len(SV9)}')

# Check amount scale - find a known cheap card
p = fetch_page({'name': 'ナゾノクサ'})
for item in (p.get('buyingPrices') or [])[:5]:
    print('search ナゾノクサ:', item.get('name'), item.get('amount'), item.get('model_number'))
