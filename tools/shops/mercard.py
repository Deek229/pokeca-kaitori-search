"""メルカード — mercardpokemon.jp（通販休業中・503。買取表 Web 版なし）。"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import requests

from shop_fetch_common import USER_AGENT

SHOP_ID = 'mercard'
SHOP_SLUG = 'mercard'

SITE_BASE = 'https://www.mercardpokemon.jp'
SEARCH_PATH = '/product-list'

_price_re = re.compile(r'(\d{1,3}(?:,\d{3})*)\s*円')


def search_url_for_card(name: str, set_tcgdex_id: str | None) -> str:
    q = f'{name} {set_tcgdex_id or ""}'.strip()
    return f'{SITE_BASE}{SEARCH_PATH}?keyword={quote(q)}'


def _parse_product_list(html: str, *, source_url: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    # ocnk 系: 商品名 + 価格の粗い抽出
    blocks = re.split(r'<li[^>]*class="[^"]*product[^"]*"', html, flags=re.I)
    for block in blocks[1:]:
        name_m = re.search(r'alt="([^"]+)"', block)
        if not name_m:
            name_m = re.search(r'>\s*([^<]{4,80})\s*<', block)
        price_m = _price_re.search(block)
        if not name_m or not price_m:
            continue
        title = name_m.group(1).strip()
        price = int(price_m.group(1).replace(',', ''))
        if price <= 0:
            continue
        entries.append({
            'title': title,
            'price_yen': price,
            'source_url': source_url,
            'note': '美品',
        })
    return entries


def load_buylist_catalog(
    *,
    session: requests.Session,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """通販サイト検索ページから買取候補を取得（503 時は空）。"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept-Language': 'ja,en;q=0.9',
        'Referer': 'https://akihabara-cardshop.com/',
    }
    session.headers.update(headers)

    try:
        resp = session.get(f'{SITE_BASE}{SEARCH_PATH}', timeout=30)
    except requests.RequestException as exc:
        return [], [SITE_BASE], f'接続エラー: {exc}'

    if resp.status_code == 503:
        return [], [SITE_BASE], (
            'mercardpokemon.jp が 503（通販サイト一時休業中）のため自動取得できません。'
            ' 検索リンクのみ設定します。ポケモン買取表の Web 版はありません。'
        )
    if resp.status_code >= 400:
        return [], [SITE_BASE], f'HTTP {resp.status_code}'

    entries = _parse_product_list(resp.text, source_url=resp.url)
    if not entries:
        return [], [resp.url], '買取表 HTML から価格行を抽出できませんでした。'
    return entries, [resp.url], None
