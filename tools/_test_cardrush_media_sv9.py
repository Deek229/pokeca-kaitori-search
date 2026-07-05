"""SV9 match test: cardrush.media vs DB cards."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import connect, ensure_db
from shop_fetch_common import list_cards
from shop_matching import pick_best_match

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def fetch_sv9_buylist() -> list[dict]:
    url = 'https://cardrush.media/pokemon/buying_prices?' + urlencode({'pack_code': 'SV9'})
    r = requests.get(url, headers=UA, timeout=60)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', r.text)
    if not m:
        return []
    props = json.loads(m.group(1))['props']['pageProps']
    entries = []
    for item in props.get('buyingPrices') or []:
        name = item.get('name') or ''
        mn = item.get('model_number') or ''
        pack = item.get('pack_code') or ''
        amount = int(item.get('amount') or 0)
        # FullComp-style label for matcher
        rarity = item.get('rarity') or ''
        r_tag = f'【{rarity}】' if rarity and rarity != '-' else ''
        title = f'{r_tag}{name}({mn}){pack}'
        entries.append({
            'title': title,
            'price_yen': amount,
            'source_url': url,
            'note': item.get('extra_difference') or '美品',
            'parsed': None,
        })
    return entries


def main() -> None:
    catalog = fetch_sv9_buylist()
    print(f'catalog entries (pack_code=SV9 only): {len(catalog)}')
    if catalog[:2]:
        print('sample:', catalog[0]['title'], catalog[0]['price_yen'])

    # Also fetch SV9a
    url9a = 'https://cardrush.media/pokemon/buying_prices?' + urlencode({'pack_code': 'SV9a'})
    r = requests.get(url9a, headers=UA, timeout=60)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', r.text)
    if m:
        for item in json.loads(m.group(1))['props']['pageProps'].get('buyingPrices') or []:
            name = item.get('name') or ''
            mn = item.get('model_number') or ''
            pack = item.get('pack_code') or ''
            rarity = item.get('rarity') or ''
            r_tag = f'【{rarity}】' if rarity and rarity != '-' else ''
            catalog.append({
                'title': f'{r_tag}{name}({mn}){pack}',
                'price_yen': int(item.get('amount') or 0),
                'source_url': url9a,
                'note': item.get('extra_difference') or '美品',
            })
    print(f'catalog with SV9a: {len(catalog)}')

    ensure_db()
    with connect() as conn:
        cards = list_cards(conn, set_tcgdex_id='SV9')
        print(f'DB SV9 cards: {len(cards)}')

        found = 0
        samples = []
        for card in cards:
            m = pick_best_match(
                catalog,
                card_name=card['name'],
                local_id=card['local_id'],
                set_tcgdex_id=card['set_tcgdex_id'],
                min_score=70,
            )
            if m:
                found += 1
                if len(samples) < 10:
                    samples.append((card['id'], card['name'], m['price_yen'], m['title'][:60]))

        print(f'\nMATCH RATE: {found}/{len(cards)} ({100*found/len(cards):.1f}%)')
        print('\nSample matches:')
        for cid, name, price, title in samples:
            print(f'  {cid} {name}: {price}円 — {title}')

        not_found_names = []
        for card in cards:
            m = pick_best_match(
                catalog, card_name=card['name'], local_id=card['local_id'],
                set_tcgdex_id=card['set_tcgdex_id'], min_score=70,
            )
            if not m:
                not_found_names.append(card['name'])
        from collections import Counter
        print('\nTop not-found (by name frequency):')
        for name, cnt in Counter(not_found_names).most_common(8):
            print(f'  {name} x{cnt}')


if __name__ == '__main__':
    main()
