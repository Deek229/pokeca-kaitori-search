"""One-off investigation script for Card Rush / Mercard buylist sources."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shop_fetch_common import USER_AGENT
from shop_matching import pick_best_match
from shops import cardrush, mercard

UA_BROWSER = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)
SHEET_ID = cardrush.SHEET_ID

SV9_SAMPLES = [
    ('sv9_033', 'リーリエのピッピex', '033'),
    ('sv9_001', 'ナゾノクサ', '001'),
    ('sv9_050', 'ピカチュウex', '050'),
    ('sv9_100', 'リーリエの決心', '100'),
    ('sv9_115', 'ナンジャモ', '115'),
    ('sv9_120', 'ボスの指令', '120'),
    ('sv9_125', 'スグリ', '125'),
    ('sv9_130', 'ゼイユ', '130'),
]


def probe(name: str, url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    h = headers or {'User-Agent': UA_BROWSER, 'Accept-Language': 'ja,en;q=0.9'}
    try:
        r = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
        text = r.text
        cells = re.findall(r'<td[^>]*>([^<]*)</td>', text[:200000])
        ref_cells = sum(1 for c in cells if c.strip() == '#REF!')
        return {
            'name': name,
            'url': url,
            'status': r.status_code,
            'len': len(text),
            'final_url': r.url,
            'ref_cells': ref_cells,
            'td_cells': len(cells),
            'has_price_yen': bool(re.search(r'\d{1,3}(?:,\d{3})*\s*円', text)),
            'has_sv9': bool(re.search(r'sv9', text, re.I)),
            'has_table': '<table' in text.lower(),
            'has_tableData': 'tableData' in text,
            'has_product_li': 'class="product' in text.lower() or 'product-list' in text.lower(),
            'title': (re.search(r'<title[^>]*>([^<]+)</title>', text, re.I) or [None, ''])[1][:100],
            'content_type': r.headers.get('Content-Type', ''),
        }
    except Exception as exc:
        return {'name': name, 'url': url, 'error': str(exc)}


def main() -> None:
    results: list[dict] = []

    cr_urls = [
        ('CR page/38 standard', 'https://www.cardrush-pokemon.jp/page/38'),
        ('CR page/39 latest', 'https://www.cardrush-pokemon.jp/page/39'),
        ('CR search SV9', f'https://www.cardrush-pokemon.jp/page/38?keyword={quote("リーリエ SV9")}'),
        ('CR product-list', 'https://www.cardrush-pokemon.jp/product-list'),
        ('CR ocnk search', f'https://www.cardrush-pokemon.jp/product-list?keyword={quote("SV9")}'),
    ]
    for n, u in cr_urls:
        results.append(probe(n, u))

    for gid, label in [('1490875147', 'latest'), ('159569114', 'standard')]:
        for fmt, url in [
            ('pubhtml', f'https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pubhtml/sheet?headers=false&gid={gid}'),
            ('csv', f'https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pub?gid={gid}&single=true&output=csv'),
            ('gviz', f'https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={gid}'),
        ]:
            results.append(probe(f'CR sheet {label} {fmt}', url))

    mc_headers_bot = {
        'User-Agent': USER_AGENT,
        'Accept-Language': 'ja,en;q=0.9',
        'Referer': 'https://akihabara-cardshop.com/',
    }
    mc_headers_browser = {
        'User-Agent': UA_BROWSER,
        'Accept-Language': 'ja,en;q=0.9',
        'Referer': 'https://akihabara-cardshop.com/',
    }
    mc_urls = [
        ('MP product-list bot', 'https://www.mercardpokemon.jp/product-list', mc_headers_bot),
        ('MP product-list browser', 'https://www.mercardpokemon.jp/product-list', mc_headers_browser),
        ('MP home browser', 'https://www.mercardpokemon.jp/', mc_headers_browser),
        ('MP search browser', f'https://www.mercardpokemon.jp/product-list?keyword={quote("リーリエ SV9")}', mc_headers_browser),
        ('mercard.jp', 'https://www.mercard.jp/', None),
        ('aki buylist', 'https://akihabara-cardshop.com/buylist', None),
        ('aki pokemon', 'https://akihabara-cardshop.com/pokemon', None),
        ('aki kaitori', 'https://akihabara-cardshop.com/kaitori', None),
        ('aki product-list', 'https://akihabara-cardshop.com/product-list', None),
    ]
    for n, u, h in mc_urls:
        results.append(probe(n, u, h))

    print('=== URL PROBE ===')
    print(json.dumps(results, ensure_ascii=False, indent=2))

    session = requests.Session()
    session.headers.update({'User-Agent': UA_BROWSER, 'Accept-Language': 'ja,en;q=0.9'})

    print('\n=== CARD RUSH MODULE ===')
    entries, sources, err = cardrush.load_buylist_catalog(session=session)
    print(f'entries={len(entries)} sources={sources} error={err}')
    if entries[:3]:
        print('sample:', entries[:3])

    print('\n=== MERCARD MODULE (bot UA) ===')
    session2 = requests.Session()
    entries2, sources2, err2 = mercard.load_buylist_catalog(session=session2)
    print(f'entries={len(entries2)} sources={sources2} error={err2}')

    print('\n=== MERCARD MODULE (browser UA) ===')
    session3 = requests.Session()
    session3.headers.update(mc_headers_browser)
    try:
        r = session3.get('https://www.mercardpokemon.jp/product-list', timeout=30)
        print(f'status={r.status_code} len={len(r.text)}')
        entries3 = mercard._parse_product_list(r.text, source_url=r.url)
        print(f'parsed entries={len(entries3)}')
        if entries3[:3]:
            print('sample:', entries3[:3])
    except Exception as exc:
        print(f'error: {exc}')

    print('\n=== SV9 MATCH TEST (if catalog available) ===')
    for shop_name, catalog in [('cardrush', entries), ('mercard_browser', entries3 if 'entries3' in dir() else [])]:
        if not catalog:
            print(f'{shop_name}: no catalog')
            continue
        found = 0
        for cid, name, lid in SV9_SAMPLES:
            m = pick_best_match(catalog, card_name=name, local_id=lid, set_tcgdex_id='SV9', min_score=70)
            if m:
                found += 1
                print(f'  {shop_name} {cid} {name}: {m.get("price_yen")} — {m.get("title","")[:60]}')
            else:
                print(f'  {shop_name} {cid} {name}: NO MATCH')
        print(f'{shop_name} match: {found}/{len(SV9_SAMPLES)}')


def analyze_sheet_and_pages() -> None:
    session = requests.Session()
    session.headers.update({'User-Agent': UA_BROWSER, 'Accept-Language': 'ja,en;q=0.9'})

    print('\n=== SHEET CELL DETAIL ===')
    for gid, label in [('159569114', 'standard'), ('1490875147', 'latest')]:
        url = (
            f'https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pubhtml/sheet'
            f'?headers=false&gid={gid}'
        )
        r = session.get(url, timeout=60)
        cells = re.findall(r'<td[^>]*>([^<]*)</td>', r.text)
        print(f'{label}: {len(cells)} cells, ref={sum(1 for c in cells if c.strip()=="#REF!")}')
        print('  first 24:', cells[:24])
        csv_r = session.get(
            f'https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pub?gid={gid}&single=true&output=csv',
            timeout=60,
        )
        print(f'  csv ({len(csv_r.text)} bytes): {csv_r.text[:120]!r}')

    print('\n=== PAGE/38 IFRAME ===')
    r = session.get('https://www.cardrush-pokemon.jp/page/38', timeout=30)
    iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', r.text)
    print('iframes:', iframes)

    print('\n=== PRODUCT-LIST (retail vs buy?) ===')
    r = session.get(
        'https://www.cardrush-pokemon.jp/product-list?keyword=' + quote('リーリエ SV9'),
        timeout=30,
    )
    blocks = re.split(r'<li[^>]*class="[^"]*product[^"]*"', r.text, flags=re.I)
    for b in blocks[1:4]:
        name_m = re.search(r'alt="([^"]+)"', b)
        price_m = re.search(r'(\d{1,3}(?:,\d{3})*)\s*円', b)
        ctx = b[:500].replace('\n', ' ')
        print('name:', name_m.group(1) if name_m else None)
        print('price:', price_m.group(0) if price_m else None)
        for kw in ('買取', '販売', '売価', '在庫', 'カート'):
            if kw in ctx:
                print(f'  has {kw}')

    print('\n=== AKIHABARA BUYLIST LINKS ===')
    for path in ('/', '/kaitori/', '/business/', '/shop/'):
        r = session.get(f'https://akihabara-cardshop.com{path}', timeout=30)
        links = re.findall(r'href="(https?://[^"]+|/[^"]+)"', r.text)
        buy = [u for u in links if any(k in u.lower() for k in ('kaitori', 'buy', '買取', 'pokemon', 'mercard'))]
        print(f'{path} status={r.status_code} buy-related links:', buy[:15])

    print('\n=== CARD RUSH CATALOG QUALITY ===')
    entries, _, err = cardrush.load_buylist_catalog(session=session)
    print(f'entries={len(entries)} err={err}')
    sv9 = [e for e in entries if 'sv9' in e['title'].lower() or 'SV9' in e['title']]
    print(f'sv9 in title: {len(sv9)}')
    if sv9[:5]:
        for e in sv9[:5]:
            print(' ', e)
    # show rows with Japanese chars in title
    jp = [e for e in entries if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', e['title'])]
    print(f'entries with Japanese title: {len(jp)} / {len(entries)}')
    if jp[:5]:
        for e in jp[:5]:
            print(' ', e)


def probe_cardrush_media() -> None:
    session = requests.Session()
    session.headers.update({'User-Agent': UA_BROWSER, 'Accept-Language': 'ja,en;q=0.9'})

    print('\n=== CARDRUSH.MEDIA & KAITORI SEARCH ===')
    urls = [
        ('cardrush.media buying_prices', 'https://cardrush.media/pokemon/buying_prices'),
        ('cardrush.media api guess', 'https://cardrush.media/api/pokemon/buying_prices'),
        ('CR phone kaitori search', 'https://www.cardrush-pokemon.jp/phone/kaitori/search?keyword=' + quote('リーリエのピッピex')),
        ('CR phone kaitori SV9', 'https://www.cardrush-pokemon.jp/phone/kaitori/search?keyword=SV9'),
        ('CR page/40', 'https://www.cardrush-pokemon.jp/page/40'),
        ('CR page/45', 'https://www.cardrush-pokemon.jp/page/45'),
    ]
    for name, url in urls:
        try:
            r = session.get(url, timeout=60)
            t = r.text
            print(f'\n--- {name} ---')
            print(f'status={r.status_code} len={len(t)} ct={r.headers.get("Content-Type","")[:50]}')
            if r.headers.get('Content-Type', '').startswith('application/json'):
                print('json sample:', t[:800])
            else:
                title = (re.search(r'<title[^>]*>([^<]+)', t, re.I) or [None, ''])[1]
                print('title:', title[:100] if title else None)
                print('has_sv9:', bool(re.search('sv9', t, re.I)))
                print('has_yen:', bool(re.search(r'\d{1,3}(?:,\d{3})*\s*円', t)))
                endpoints = sorted(set(re.findall(
                    r'https?://[^\s"\'<>]+(?:buying|kaitori|buy|api|json)[^\s"\'<>]*', t, re.I
                )))
                if endpoints:
                    print('endpoints:', endpoints[:8])
                if 'cardrush.media' in url and r.status_code == 200:
                    print('body head:', t[:2000])
        except Exception as exc:
            print(f'{name} error: {exc}')

    print('\n=== PRODUCT-LIST SAMPLE (retail check) ===')
    try:
        r = session.get(
            'https://www.cardrush-pokemon.jp/product-list?keyword=' + quote('リーリエ SV9'),
            timeout=60,
        )
        blocks = re.split(r'<li[^>]*class="[^"]*product[^"]*"', r.text, flags=re.I)
        for b in blocks[1:3]:
            name_m = re.search(r'alt="([^"]+)"', b)
            price_m = re.search(r'(\d{1,3}(?:,\d{3})*)\s*円', b)
            flags = [kw for kw in ('カート', '買取', '販売', '在庫', '売り切れ') if kw in b]
            print('name:', (name_m.group(1) if name_m else None))
            print('price:', (price_m.group(0) if price_m else None), 'flags:', flags)
    except Exception as exc:
        print('product-list error:', exc)


def probe_cardrush_media_api() -> None:
    session = requests.Session()
    session.headers.update({
        'User-Agent': UA_BROWSER,
        'Accept-Language': 'ja,en;q=0.9',
        'Accept': 'application/json, text/plain, */*',
    })

    print('\n=== CARDRUSH.MEDIA API ===')
    api_urls = [
        'https://cardrush.media/buying_prices_card_titles',
        'https://cardrush.media/pokemon/buying_prices_card_titles',
        'https://cardrush.media/api/buying_prices_card_titles',
        'https://cardrush.media/pokemon/buying_prices.json',
    ]
    for url in api_urls:
        try:
            r = session.get(url, timeout=60)
            print(f'{url}')
            print(f'  status={r.status_code} ct={r.headers.get("Content-Type", "")}')
            print(f'  body head: {r.text[:400]}')
        except Exception as exc:
            print(f'{url} error: {exc}')

    print('\n=== KAITORI SEARCH ===')
    for kw in ('リーリエのピッピex', 'SV9', 'バトルパートナーズ'):
        url = f'https://www.cardrush-pokemon.jp/kaitori/search?keyword={quote(kw)}'
        r = session.get(url, timeout=60)
        print(f'keyword={kw} status={r.status_code} len={len(r.text)}')
        ct = r.headers.get('Content-Type', '')
        if 'json' in ct:
            print(r.text[:600])
        else:
            prices = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*円', r.text)
            print(f'  yen hits={len(prices)} sample={prices[:5]}')
            if 'sv9' in r.text.lower():
                print('  contains sv9')

    print('\n=== CARDRUSH.MEDIA __NEXT_DATA__ ===')
    r = session.get('https://cardrush.media/pokemon/buying_prices', timeout=60)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', r.text)
    if m:
        data = json.loads(m.group(1))
        print('keys:', list(data.keys()))
        props = data.get('props', {}).get('pageProps', {})
        print('pageProps keys:', list(props.keys())[:20])
        for k, v in props.items():
            if isinstance(v, (list, dict)):
                print(f'  {k}: type={type(v).__name__}', end='')
                if isinstance(v, list):
                    print(f' len={len(v)}', end='')
                    if v:
                        print(f' sample0={str(v[0])[:120]}', end='')
                elif isinstance(v, dict):
                    print(f' keys={list(v.keys())[:8]}', end='')
                print()
        # save for inspection
        out = Path(__file__).resolve().parents[1] / 'data' / 'cardrush_media_next_data_sample.json'
        out.write_text(json.dumps(props, ensure_ascii=False, indent=2)[:50000], encoding='utf-8')
        print(f'saved sample to {out.name}')
    else:
        print('no __NEXT_DATA__ found')

    print('\n=== SV9 MATCH via cardrush.media ===')
    if m:
        props = json.loads(m.group(1)).get('props', {}).get('pageProps', {})
        catalog = []
        # try common shapes
        for key in ('buyingPrices', 'cards', 'items', 'data', 'initialData'):
            val = props.get(key)
            if isinstance(val, list) and val:
                catalog = val
                print(f'using pageProps.{key} ({len(val)} items)')
                break
        if not catalog:
            # flatten all lists in pageProps
            for k, v in props.items():
                if isinstance(v, list) and len(v) > 10:
                    catalog = v
                    print(f'using pageProps.{k} ({len(v)} items)')
                    break
        if catalog:
            sample_item = catalog[0]
            print('item keys/sample:', sample_item if isinstance(sample_item, dict) else sample_item)
            entries = []
            for item in catalog:
                if not isinstance(item, dict):
                    continue
                title = item.get('title') or item.get('name') or item.get('card_name') or ''
                price = item.get('price') or item.get('buying_price') or item.get('price_yen')
                if title and price:
                    entries.append({'title': str(title), 'price_yen': int(str(price).replace(',', ''))})
            print(f'parsed entries={len(entries)}')
            if entries:
                found = 0
                for cid, name, lid in SV9_SAMPLES:
                    match = pick_best_match(
                        entries, card_name=name, local_id=lid, set_tcgdex_id='SV9', min_score=70,
                    )
                    if match:
                        found += 1
                        print(f'  MATCH {cid}: {match.get("price_yen")} — {match.get("title","")[:60]}')
                    else:
                        print(f'  NO MATCH {cid} {name}')
                print(f'match rate: {found}/{len(SV9_SAMPLES)}')
        else:
            print('could not find card list in pageProps')


if __name__ == '__main__':
    main()
    analyze_sheet_and_pages()
    probe_cardrush_media()
    probe_cardrush_media_api()
