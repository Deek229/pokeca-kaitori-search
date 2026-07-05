"""カード検索・詳細・買取価格取得"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from db import connect

_card_num_re = re.compile(r'^(\d{1,3})(?:/(\d{1,3}))?$')

_LATEST_BUYBACK_SQL = '''
    SELECT bp.*, sh.name AS shop_name, sh.slug AS shop_slug, sh.website_url AS shop_url
    FROM buyback_prices bp
    JOIN shops sh ON sh.id = bp.shop_id
    INNER JOIN (
        SELECT card_id, shop_id, MAX(as_of_date) AS max_date
        FROM buyback_prices
        GROUP BY card_id, shop_id
    ) latest ON bp.card_id = latest.card_id
        AND bp.shop_id = latest.shop_id
        AND bp.as_of_date = latest.max_date
    WHERE bp.card_id = ?
    ORDER BY bp.price_yen DESC, sh.name
'''


def _normalize_query(q: str) -> str:
    return q.strip()


def _build_search_pattern(q: str) -> str:
    return f'%{q.strip()}%'


def _is_reference_shop(shop_slug: str) -> bool:
    return shop_slug == 'magi'


def _shop_search_url(shop_slug: str, *, name: str, set_tcgdex_id: str | None) -> str | None:
    """価格未取得時にショップ内検索へ誘導する URL。"""
    q = quote(f'{name} {set_tcgdex_id or ""}'.strip())
    if shop_slug == 'cardrush':
        return f'https://www.cardrush-pokemon.jp/page/38?keyword={q}'
    if shop_slug == 'mercard':
        return f'https://www.mercardpokemon.jp/product-list?keyword={q}'
    if shop_slug == 'fullcomp':
        return f'https://www.fullcomp.jp/honatsugi/kaitori/19628'
    return None


def _price_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item['is_reference'] = _is_reference_shop(item.get('shop_slug') or '')
    item['price_label'] = 'Magi 参考価格' if item['is_reference'] else '買取'
    return item


def list_sets() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            '''
            SELECT s.*, COUNT(c.id) AS card_count
            FROM sets s
            LEFT JOIN cards c ON c.set_id = s.id
            GROUP BY s.id
            ORDER BY s.release_date DESC, s.name
            '''
        ).fetchall()
    return [dict(r) for r in rows]


_SHOP_SLUG_ORDER = ('cardrush', 'mercard', 'fullcomp', 'magi')
_DEFAULT_SEARCH_LIMIT = 50


def _search_where(q: str, set_id: str | None) -> tuple[list[str], list[Any]]:
    params: list[Any] = []
    where: list[str] = []

    if set_id:
        where.append('c.set_id = ?')
        params.append(set_id)

    if q:
        num_match = _card_num_re.match(q)
        if num_match:
            local_id = num_match.group(1).zfill(3)
            where.append('(c.local_id = ? OR c.search_text LIKE ? OR c.name LIKE ?)')
            params.extend([local_id, _build_search_pattern(q), _build_search_pattern(q)])
        else:
            where.append('(c.name LIKE ? OR c.search_text LIKE ? OR c.local_id LIKE ?)')
            pattern = _build_search_pattern(q)
            params.extend([pattern, pattern, pattern])

    return where, params


def count_search_cards(
    q: str | None = None,
    set_id: str | None = None,
) -> int:
    q = _normalize_query(q or '')
    set_id = resolve_set_id(set_id)
    where, params = _search_where(q, set_id)
    sql = '''
        SELECT COUNT(DISTINCT c.id)
        FROM cards c
        JOIN sets s ON s.id = c.set_id
    '''
    if where:
        sql += ' WHERE ' + ' AND '.join(where)

    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def resolve_set_id(set_id: str | None) -> str | None:
    """内部 id（sv9）または TCGdex id（SV9）を DB の set id に正規化。"""
    if not set_id:
        return None
    sid = set_id.strip()
    if not sid:
        return None
    with connect() as conn:
        row = conn.execute(
            '''
            SELECT id FROM sets
            WHERE id = ? OR lower(tcgdex_id) = lower(?)
            ''',
            (sid.lower(), sid),
        ).fetchone()
    return row['id'] if row else sid.lower()


def search_cards(
    q: str | None = None,
    set_id: str | None = None,
    limit: int | None = _DEFAULT_SEARCH_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = _normalize_query(q or '')
    set_id = resolve_set_id(set_id)
    if set_id and not q:
        limit = None
        offset = 0
    where, params = _search_where(q, set_id)

    sql = '''
        SELECT c.*, s.name AS set_name, s.tcgdex_id AS set_tcgdex_id,
               MAX(latest_bp.price_yen) AS best_price,
               MAX(latest_bp.as_of_date) AS latest_as_of
        FROM cards c
        JOIN sets s ON s.id = c.set_id
        LEFT JOIN (
            SELECT bp.card_id, bp.price_yen, bp.as_of_date
            FROM buyback_prices bp
            INNER JOIN (
                SELECT card_id, shop_id, MAX(as_of_date) AS max_date
                FROM buyback_prices
                GROUP BY card_id, shop_id
            ) mx ON bp.card_id = mx.card_id AND bp.shop_id = mx.shop_id AND bp.as_of_date = mx.max_date
        ) latest_bp ON latest_bp.card_id = c.id
    '''
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += '''
        GROUP BY c.id
        ORDER BY s.release_date DESC, CAST(c.local_id AS INTEGER), c.name
    '''
    if limit is not None:
        sql += ' LIMIT ? OFFSET ?'
        params.extend([limit, offset])

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def list_shops() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute('SELECT * FROM shops ORDER BY name').fetchall()
    shops = [dict(r) for r in rows]
    order = {slug: idx for idx, slug in enumerate(_SHOP_SLUG_ORDER)}
    shops.sort(key=lambda s: (order.get(s['slug'], len(_SHOP_SLUG_ORDER)), s['name']))
    return shops


def _empty_price_row(shop: dict[str, Any], *, card_name: str = '', set_tcgdex_id: str | None = None) -> dict[str, Any]:
    slug = shop['slug']
    is_reference = _is_reference_shop(slug)
    search_url = _shop_search_url(slug, name=card_name, set_tcgdex_id=set_tcgdex_id) if card_name else None
    return {
        'shop_id': shop['id'],
        'shop_name': shop['name'],
        'shop_slug': slug,
        'shop_url': shop.get('website_url'),
        'price_yen': None,
        'condition_note': '—',
        'as_of_date': '—',
        'product_url': search_url,
        'is_reference': is_reference,
        'price_label': 'Magi 参考価格' if is_reference else '買取',
        'has_price': False,
        'is_search_link': bool(search_url),
    }


def _merge_shop_prices(
    prices: list[dict[str, Any]],
    shops: list[dict[str, Any]],
    *,
    card_name: str = '',
    set_tcgdex_id: str | None = None,
) -> list[dict[str, Any]]:
    by_slug = {p['shop_slug']: p for p in prices}
    merged: list[dict[str, Any]] = []
    for shop in shops:
        slug = shop['slug']
        if slug in by_slug:
            row = by_slug[slug]
            row['has_price'] = row.get('price_yen') is not None
            row['is_search_link'] = False
            merged.append(row)
        else:
            merged.append(_empty_price_row(shop, card_name=card_name, set_tcgdex_id=set_tcgdex_id))
    return merged


def get_card(card_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            '''
            SELECT c.*, s.name AS set_name, s.tcgdex_id AS set_tcgdex_id,
                   s.series_name, s.release_date AS set_release_date
            FROM cards c
            JOIN sets s ON s.id = c.set_id
            WHERE c.id = ?
            ''',
            (card_id,),
        ).fetchone()
        if not row:
            return None
        card = dict(row)
        prices = conn.execute(_LATEST_BUYBACK_SQL, (card_id,)).fetchall()
        shops = list_shops()
        priced_rows = [_price_row(dict(p)) for p in prices]
        for row in priced_rows:
            row['has_price'] = True
        card['prices'] = _merge_shop_prices(
            priced_rows,
            shops,
            card_name=card['name'],
            set_tcgdex_id=card.get('set_tcgdex_id'),
        )
        priced = [p for p in card['prices'] if p.get('has_price')]
        card['best_price'] = max((p['price_yen'] for p in priced), default=None)
        card['latest_as_of'] = max(
            (p['as_of_date'] for p in priced if p.get('as_of_date') and p['as_of_date'] != '—'),
            default=None,
        )

        history_rows = conn.execute(
            '''
            SELECT ph.recorded_at, ph.price_yen, ph.shop_id, sh.name AS shop_name, sh.slug AS shop_slug
            FROM price_history ph
            JOIN shops sh ON sh.id = ph.shop_id
            WHERE ph.card_id = ?
            ORDER BY ph.recorded_at ASC, sh.name
            ''',
            (card_id,),
        ).fetchall()
        history = [dict(h) for h in history_rows]
        card['price_history'] = history
        card['price_history_json'] = json.dumps(_build_chart_series(history), ensure_ascii=False)
        card['has_price_chart'] = _has_chart_data(history)
        card['chart_point_count'] = len(history)
        card['chart_fetch_count'] = _chart_fetch_count(history)
        return card


def _chart_time_key(recorded_at: str | None) -> str:
    """同一日内の複数取得も区別するラベルキー。"""
    if not recorded_at:
        return ''
    # ISO: 2026-06-22T12:34:56+09:00 → 2026-06-22 12:34
    text = recorded_at.replace('T', ' ')
    return text[:16] if len(text) >= 16 else text[:10]


def _build_chart_series(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Chart.js 用: ショップ別 + 全店平均の {labels, datasets}。"""
    by_shop: dict[str, dict[str, Any]] = {}
    all_keys: set[str] = set()

    for row in history:
        slug = row['shop_slug']
        time_key = _chart_time_key(row.get('recorded_at'))
        if not time_key:
            continue
        all_keys.add(time_key)
        bucket = by_shop.setdefault(
            slug,
            {'label': row['shop_name'], 'is_reference': _is_reference_shop(slug), 'points': {}},
        )
        bucket['points'][time_key] = row['price_yen']

    labels = sorted(all_keys)
    datasets = []
    colors = {
        'cardrush': '#ffd54f',
        'mercard': '#4fc3f7',
        'fullcomp': '#66bb6a',
        'magi': '#ab47bc',
    }
    shop_labels_ja = {
        'cardrush': 'カードラッシュ',
        'mercard': 'メルカード',
        'fullcomp': 'フルコンプ',
        'magi': 'Magi',
    }
    for slug, data in sorted(by_shop.items(), key=lambda x: x[1]['label']):
        base = shop_labels_ja.get(slug, data['label'])
        label = f'{base}（参考）' if data['is_reference'] else base
        datasets.append({
            'label': label,
            'data': [data['points'].get(k) for k in labels],
            'borderColor': colors.get(slug, '#9aa8c7'),
            'backgroundColor': colors.get(slug, '#9aa8c7') + '33',
            'spanGaps': True,
            'tension': 0.2,
        })

    # 買取店舗（参考価格の Magi を除く）の当日平均
    buyback_slugs = [s for s, d in by_shop.items() if not d['is_reference']]
    avg_data: list[int | None] = []
    for k in labels:
        prices = [
            by_shop[s]['points'][k]
            for s in buyback_slugs
            if k in by_shop[s]['points'] and by_shop[s]['points'][k] is not None
        ]
        avg_data.append(round(sum(prices) / len(prices)) if prices else None)

    if any(v is not None for v in avg_data):
        datasets.append({
            'label': '全店平均',
            'data': avg_data,
            'borderColor': '#e0e6f0',
            'backgroundColor': 'transparent',
            'borderDash': [8, 4],
            'borderWidth': 2,
            'spanGaps': True,
            'tension': 0.2,
            'pointRadius': 3,
        })

    return {'labels': labels, 'datasets': datasets}


def _chart_fetch_count(history: list[dict[str, Any]]) -> int:
    return len(history)


def _has_chart_data(history: list[dict[str, Any]]) -> bool:
    """履歴が2件以上あればグラフ表示（同日の再取得も可）。"""
    return len(history) >= 2


def popular_cards(limit: int = 8) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            '''
            SELECT c.*, s.name AS set_name,
                   MAX(latest_bp.price_yen) AS best_price,
                   MAX(latest_bp.as_of_date) AS latest_as_of
            FROM cards c
            JOIN sets s ON s.id = c.set_id
            JOIN (
                SELECT bp.card_id, bp.price_yen, bp.as_of_date
                FROM buyback_prices bp
                INNER JOIN (
                    SELECT card_id, shop_id, MAX(as_of_date) AS max_date
                    FROM buyback_prices
                    GROUP BY card_id, shop_id
                ) mx ON bp.card_id = mx.card_id AND bp.shop_id = mx.shop_id AND bp.as_of_date = mx.max_date
            ) latest_bp ON latest_bp.card_id = c.id
            GROUP BY c.id
            ORDER BY best_price DESC
            LIMIT ?
            ''',
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
