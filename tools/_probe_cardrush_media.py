"""Quick probe: cardrush.media API only."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shop_matching import pick_best_match

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'ja,en;q=0.9',
    'Accept': 'application/json, text/plain, */*',
}
SV9 = [
    ('sv9_033', 'リーリエのピッピex', '033'),
    ('sv9_001', 'ナゾノクサ', '001'),
    ('sv9_050', 'ピカチュウex', '050'),
    ('sv9_100', 'リーリエの決心', '100'),
    ('sv9_115', 'ナンジャモ', '115'),
]

s = requests.Session()
s.headers.update(UA)

print('=== API endpoints ===')
for url in [
    'https://cardrush.media/buying_prices_card_titles',
    'https://cardrush.media/pokemon/buying_prices_card_titles',
]:
    r = s.get(url, timeout=60)
    print(url, r.status_code, r.headers.get('Content-Type', ''))
    print(r.text[:600])
    print()

print('=== __NEXT_DATA__ ===')
r = s.get('https://cardrush.media/pokemon/buying_prices', timeout=60)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', r.text)
if not m:
    print('no next data')
    sys.exit(0)

data = json.loads(m.group(1))
props = data.get('props', {}).get('pageProps', {})
print('pageProps keys:', list(props.keys()))
for k, v in props.items():
    if isinstance(v, list):
        print(f'  {k}: list len={len(v)}', str(v[0])[:150] if v else '')
    elif isinstance(v, dict):
        print(f'  {k}: dict keys={list(v.keys())[:12]}')

catalog: list[dict] = []
for key, val in props.items():
    if isinstance(val, list) and len(val) > 50:
        catalog = [x for x in val if isinstance(x, dict)]
        print(f'\nUsing {key}: {len(catalog)} dict items')
        if catalog:
            print('sample keys:', list(catalog[0].keys()))
            print('sample:', catalog[0])
        break

entries = []
for item in catalog:
    title = (
        item.get('title') or item.get('name') or item.get('card_name')
        or item.get('card_title') or item.get('label') or ''
    )
    price = (
        item.get('price') or item.get('buying_price') or item.get('buyingPrice')
        or item.get('price_yen') or item.get('amount')
    )
    if title and price is not None:
        entries.append({
            'title': str(title),
            'price_yen': int(re.sub(r'[^\d]', '', str(price)) or 0),
        })

print(f'\nentries with price: {len(entries)}')
if entries[:3]:
    print('first 3:', entries[:3])

found = 0
for cid, name, lid in SV9:
    match = pick_best_match(entries, card_name=name, local_id=lid, set_tcgdex_id='SV9', min_score=70)
    if match:
        found += 1
        print(f'MATCH {cid}: {match["price_yen"]} — {match["title"][:70]}')
    else:
        print(f'NO MATCH {cid} {name}')
print(f'match: {found}/{len(SV9)}')

print('\n=== kaitori search ===')
for kw in ('リーリエのピッピex', 'SV9'):
    url = f'https://www.cardrush-pokemon.jp/kaitori/search?keyword={quote(kw)}'
    r = s.get(url, timeout=60)
    print(kw, r.status_code, len(r.text), 'json' in r.headers.get('Content-Type', ''))
    prices = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*円', r.text)
    print('  prices:', prices[:8])
