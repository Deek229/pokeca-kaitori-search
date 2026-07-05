"""フルコンプ — 店舗買取表 HTML から tableData を取得。"""
from __future__ import annotations

import ast
import re
from typing import Any
from urllib.parse import quote

import requests

from shop_fetch_common import USER_AGENT
from shop_matching import parse_listing_label

SHOP_ID = 'fullcomp'
SHOP_SLUG = 'fullcomp'

# 全店同一価格のため代表店舗の買取表を使用
DEFAULT_BUYLIST_URLS = [
    'https://www.fullcomp.jp/honatsugi/kaitori/19628',  # ポケモンカード 買取表（sv9 等を含む）
]

_table_data_re = re.compile(r'var tableData = \[([\s\S]*?)\];', re.MULTILINE)


def fetch_page_html(url: str, *, session: requests.Session) -> str:
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or 'utf-8'
    return resp.text


def parse_table_data(html: str) -> list[dict[str, Any]]:
    m = _table_data_re.search(html)
    if not m:
        return []
    raw = '[' + m.group(1).strip().rstrip(',') + ']'
    try:
        rows = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return []

    entries: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        label = str(row[4]).strip()
        if not label:
            continue
        parsed = parse_listing_label(label)
        price_raw = str(row[-1]).strip().replace(',', '')
        if not price_raw.isdigit():
            continue
        entries.append({
            'title': label,
            'parsed': parsed,
            'price_yen': int(price_raw),
            'note': str(row[5]).strip() if len(row) > 5 else '',
            'source_url': None,
        })
    return entries


def load_buylist_catalog(
    urls: list[str] | None = None,
    *,
    session: requests.Session,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """複数買取表をマージ（同一 title は後勝ち）。"""
    urls = urls or DEFAULT_BUYLIST_URLS
    by_title: dict[str, dict[str, Any]] = {}
    fetched_urls: list[str] = []
    error: str | None = None

    for url in urls:
        html = fetch_page_html(url, session=session)
        fetched_urls.append(url)
        rows = parse_table_data(html)
        if not rows:
            error = error or f'買取表から tableData を読み取れませんでした: {url}'
            continue
        for entry in rows:
            entry['source_url'] = url
            by_title[entry['title']] = entry

    entries = list(by_title.values())
    if not entries and not error:
        error = '買取表カタログが空です'
    return entries, fetched_urls, error


def search_url_for_card(name: str, set_tcgdex_id: str | None) -> str:
    q = f'{name} {set_tcgdex_id or ""}'.strip()
    return f'https://www.fullcomp.jp/honatsugi/kaitori/19628?q={quote(q)}'
