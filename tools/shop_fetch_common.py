"""買取価格取得の共通処理（進捗・DB・カード一覧）。"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from db import connect, ensure_db

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
USER_AGENT = 'PokecaBuybackSearch/0.1 (+local; buyback-fetch)'

SET_SEARCH_HINTS: dict[str, str] = {
    'ポケモンカード151': '151',
    'バトルパートナーズ': 'SV9',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def progress_path(shop_slug: str) -> Path:
    return DATA_DIR / f'{shop_slug}_price_fetch_progress.json'


def _parse_progress_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def progress_run_date(progress: dict[str, Any]) -> date | None:
    """進捗ファイルの実行日（カレンダー日）。"""
    return _parse_progress_date(progress.get('as_of_date')) or _parse_progress_date(
        progress.get('last_run_at')
    )


def resume_skip_ids(
    progress: dict[str, Any],
    *,
    resume: bool,
    refresh: bool,
    force: bool,
) -> set[str]:
    """--resume 時のみ、同日に完了済みのカード ID を返す。日跨ぎ・--refresh・--force はスキップなし。"""
    if force or refresh or not resume:
        return set()
    if progress_run_date(progress) != date.today():
        return set()
    return set(progress.get('completed_card_ids') or [])


def load_progress(shop_slug: str) -> dict[str, Any]:
    path = progress_path(shop_slug)
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {
        'completed_card_ids': [],
        'failed': [],
        'stats': {'found': 0, 'not_found': 0, 'errors': 0, 'skipped': 0},
        'last_run_at': None,
        'as_of_date': None,
        'catalog_loaded_at': None,
    }


def save_progress(shop_slug: str, progress: dict[str, Any], *, as_of_date: str | None = None) -> None:
    path = progress_path(shop_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    progress['last_run_at'] = now_iso()
    if as_of_date:
        progress['as_of_date'] = as_of_date
    path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding='utf-8')


def upsert_buyback_price(
    conn,
    *,
    card_id: str,
    shop_id: str,
    price_yen: int,
    condition_note: str,
    as_of_date: str,
    recorded_at: str,
    product_url: str | None,
) -> None:
    conn.execute(
        '''
        INSERT INTO buyback_prices (card_id, shop_id, price_yen, condition_note, as_of_date, product_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id, shop_id, as_of_date) DO UPDATE SET
            price_yen = excluded.price_yen,
            condition_note = excluded.condition_note,
            product_url = excluded.product_url
        ''',
        (card_id, shop_id, price_yen, condition_note, as_of_date, product_url),
    )
    conn.execute(
        '''
        INSERT INTO price_history (card_id, shop_id, price_yen, recorded_at, condition_note, product_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (card_id, shop_id, price_yen, recorded_at, condition_note, product_url),
    )


def list_cards(
    conn,
    *,
    set_tcgdex_id: str | None = None,
    limit: int | None = None,
    skip_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    skip_ids = skip_ids or set()
    params: list[Any] = []
    where = ''
    if set_tcgdex_id:
        where = ' WHERE s.tcgdex_id = ?'
        params.append(set_tcgdex_id.upper())

    rows = conn.execute(
        f'''
        SELECT c.id, c.name, c.local_id, c.tcgdex_id, s.name AS set_name, s.tcgdex_id AS set_tcgdex_id
        FROM cards c
        JOIN sets s ON s.id = c.set_id
        {where}
        ORDER BY CAST(c.local_id AS INTEGER), c.name
        ''',
        params,
    ).fetchall()
    cards = [dict(r) for r in rows if r['id'] not in skip_ids]
    if limit is not None:
        cards = cards[:limit]
    return cards


def build_search_keyword(name: str, set_name: str, set_tcgdex_id: str | None) -> str:
    hint = SET_SEARCH_HINTS.get(set_name) or (set_tcgdex_id or '')
    parts = [name.strip()]
    if hint:
        parts.append(hint)
    return ' '.join(p for p in parts if p)
