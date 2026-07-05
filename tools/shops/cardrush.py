"""カードラッシュ — cardrush.media 買取表（旧 Google シートは #REF! で失效）。"""
from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote, urlencode

import requests

from shop_fetch_common import USER_AGENT
from shop_matching import parse_listing_label

SHOP_ID = 'cardrush'
SHOP_SLUG = 'cardrush'

MEDIA_BUYLIST_URL = 'https://cardrush.media/pokemon/buying_prices'
# 旧ソース（参照用・現在は #REF!）
SHEET_ID = '2PACX-1vQT3Q9qDbZUpnP3_WH2I5qw8O-U_PqXVhhoIzH2o-tSzeDND9FTuoGKbZiNHTbrzTgKAUA2_SvXFh_2'
BUYLIST_PAGES = {
    'latest': ('https://www.cardrush-pokemon.jp/page/39', '1490875147'),
    'standard': ('https://www.cardrush-pokemon.jp/page/38', '159569114'),
}

_next_data_re = re.compile(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', re.I)
_iframe_gid_re = re.compile(
    r'docs\.google\.com/spreadsheets/d/e/[^/]+/pubhtml\?[^"\']*gid=(\d+)',
    re.I,
)


def search_url_for_card(name: str, set_tcgdex_id: str | None) -> str:
    q = f'{name} {set_tcgdex_id or ""}'.strip()
    params = {'name': name}
    if set_tcgdex_id:
        params['pack_code'] = set_tcgdex_id
    return f'{MEDIA_BUYLIST_URL}?{urlencode(params)}'


def _item_to_entry(item: dict[str, Any], *, source_url: str) -> dict[str, Any] | None:
    name = (item.get('name') or '').strip()
    model_number = (item.get('model_number') or '').strip()
    pack_code = (item.get('pack_code') or '').strip()
    rarity = (item.get('rarity') or '').strip()
    amount = item.get('amount')
    if not name or amount is None:
        return None
    try:
        price_yen = int(amount)
    except (TypeError, ValueError):
        return None
    if price_yen <= 0:
        return None

    rarity_tag = f'【{rarity}】' if rarity and rarity != '-' else ''
    title = f'{rarity_tag}{name}({model_number}){pack_code}'
    note = (item.get('extra_difference') or '').strip() or '美品'
    return {
        'title': title,
        'parsed': parse_listing_label(title),
        'price_yen': price_yen,
        'source_url': source_url,
        'note': note,
    }


def _fetch_media_page(
    *,
    session: requests.Session,
    page: int = 1,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], int, str]:
    """cardrush.media の1ページ分を取得。戻り値: (items, lastPage, url)。"""
    params = {'page': str(page), 'limit': str(limit)}
    url = f'{MEDIA_BUYLIST_URL}?{urlencode(params)}'
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    m = _next_data_re.search(resp.text)
    if not m:
        return [], 0, url
    props = json.loads(m.group(1)).get('props', {}).get('pageProps', {})
    items = props.get('buyingPrices') or []
    last_page = int(props.get('lastPage') or 1)
    return items, last_page, url


def _load_media_catalog(*, session: requests.Session) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """cardrush.media から全ページの買取表を取得。"""
    entries: list[dict[str, Any]] = []
    sources: list[str] = [MEDIA_BUYLIST_URL]

    try:
        items, last_page, first_url = _fetch_media_page(session=session, page=1)
    except requests.RequestException as exc:
        return [], sources, f'cardrush.media 接続エラー: {exc}'

    print(f'  [cardrush] 買取表 全 {last_page} ページを取得します（1ページあたり最大100件）')

    for item in items:
        row = _item_to_entry(item, source_url=first_url)
        if row:
            entries.append(row)

    for page in range(2, last_page + 1):
        if page == 2 or page % 10 == 0 or page == last_page:
            print(f'  [cardrush] 買取表ページ {page}/{last_page} を取得中...')
        time.sleep(0.3)
        try:
            items, _, url = _fetch_media_page(session=session, page=page)
        except requests.RequestException:
            continue
        sources.append(url)
        for item in items:
            row = _item_to_entry(item, source_url=url)
            if row:
                entries.append(row)

    if entries:
        return entries, sources, None
    return [], sources, 'cardrush.media から買取行を取得できませんでした。'


def _fetch_sheet_rows(gid: str, *, session: requests.Session) -> list[list[str]]:
    url = (
        f'https://docs.google.com/spreadsheets/d/e/{SHEET_ID}/pubhtml/sheet'
        f'?headers=false&gid={gid}'
    )
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException:
        return []
    cells = re.findall(r'<td[^>]*>([^<]*)</td>', resp.text)
    if not cells or all(c in ('', '#REF!') for c in cells):
        return []
    rows: list[list[str]] = []
    row: list[str] = []
    for cell in cells:
        row.append(cell.strip())
        if len(row) >= 6:
            rows.append(row)
            row = []
    return rows


def _discover_gids(*, session: requests.Session) -> list[tuple[str, str]]:
    gids: list[tuple[str, str]] = []
    for key, (page_url, default_gid) in BUYLIST_PAGES.items():
        gid = default_gid
        try:
            resp = session.get(page_url, timeout=30)
            if resp.ok:
                found = _iframe_gid_re.search(resp.text)
                if found and found.group(1) != '0':
                    gid = found.group(1)
        except requests.RequestException:
            pass
        gids.append((key, gid))
    return gids


def _load_sheet_catalog(*, session: requests.Session) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """旧 Google スプレッドシート買取表（#REF! 時は空）。"""
    entries: list[dict[str, Any]] = []
    sources: list[str] = []

    for key, gid in _discover_gids(session=session):
        page_url = BUYLIST_PAGES[key][0]
        sources.append(page_url)
        rows = _fetch_sheet_rows(gid, session=session)
        if not rows:
            continue
        for row in rows:
            if len(row) < 4:
                continue
            label = row[1] if len(row) > 1 else ''
            price_raw = re.sub(r'[^\d]', '', row[3] if len(row) > 3 else '')
            if not label or not price_raw:
                continue
            entries.append({
                'title': label,
                'price_yen': int(price_raw),
                'source_url': page_url,
                'note': '美品',
            })

    if not entries:
        return [], sources, (
            'Google スプレッドシートの公開ビューが #REF! のため自動取得できません。'
        )
    return entries, sources, None


def load_buylist_catalog(
    *,
    session: requests.Session,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """買取表カタログ。cardrush.media を優先、失敗時は旧シートを試行。"""
    session.headers.setdefault('User-Agent', USER_AGENT)
    session.headers.setdefault('Accept-Language', 'ja,en;q=0.9')

    entries, sources, error = _load_media_catalog(session=session)
    if entries:
        return entries, sources, None

    sheet_entries, sheet_sources, sheet_error = _load_sheet_catalog(session=session)
    if sheet_entries:
        return sheet_entries, sheet_sources, None

    combined_error = error or sheet_error or '買取表を取得できませんでした。'
    return [], sources or sheet_sources, (
        f'{combined_error} 買取表ページへのリンクのみ設定します。'
    )
