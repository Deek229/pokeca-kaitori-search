"""TCGdex API からカードマスタを取得・DB投入する共通ロジック"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from config import TCGDEX_API_BASE
from db import connect, ensure_db

DEFAULT_DELAY_SEC = 0.5
MAX_RETRIES = 5
RETRY_BACKOFF_SEC = 2.0
PROGRESS_FILE = Path(__file__).resolve().parents[1] / 'data' / 'tcgdex_import_progress.json'

_last_request_at = 0.0


def _throttle(delay_sec: float) -> None:
    global _last_request_at
    if delay_sec <= 0:
        return
    elapsed = time.monotonic() - _last_request_at
    if elapsed < delay_sec:
        time.sleep(delay_sec - elapsed)
    _last_request_at = time.monotonic()


def fetch_json(path: str, *, delay_sec: float = DEFAULT_DELAY_SEC) -> Any:
    """GET {TCGDEX_API_BASE}/{path} with rate limit and retries."""
    segments = path.lstrip('/').split('/')
    encoded_path = '/'.join(quote(segment, safe='') for segment in segments)
    url = f'{TCGDEX_API_BASE}/{encoded_path}'
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        _throttle(delay_sec)
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 429:
                wait = RETRY_BACKOFF_SEC * (2 ** attempt)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 >= MAX_RETRIES:
                break
            wait = RETRY_BACKOFF_SEC * (2 ** attempt)
            time.sleep(wait)

    raise RuntimeError(f'API request failed after {MAX_RETRIES} retries: {url}') from last_error


def fetch_all_set_summaries(*, delay_sec: float = DEFAULT_DELAY_SEC) -> list[dict[str, Any]]:
    data = fetch_json('sets', delay_sec=delay_sec)
    if not isinstance(data, list):
        raise RuntimeError('Unexpected /sets response (expected list)')
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in data:
        set_id = item.get('id')
        if not set_id or set_id in seen:
            continue
        seen.add(set_id)
        unique.append(item)
    return unique


def fetch_set_detail(set_id: str, *, delay_sec: float = DEFAULT_DELAY_SEC) -> dict[str, Any]:
    data = fetch_json(f'sets/{set_id}', delay_sec=delay_sec)
    if not isinstance(data, dict):
        raise RuntimeError(f'Unexpected /sets/{set_id} response')
    return data


def _search_text(set_name: str, local_id: str, name: str, tcgdex_id: str) -> str:
    return f'{name} {set_name} {local_id} {tcgdex_id}'.lower()


def upsert_set_and_cards(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    """Upsert one set and its cards. Returns card count."""
    set_id = data['id'].lower()
    set_row = {
        'id': set_id,
        'tcgdex_id': data['id'],
        'name': data['name'],
        'series_name': (data.get('serie') or {}).get('name'),
        'release_date': data.get('releaseDate'),
        'card_count_official': (data.get('cardCount') or {}).get('official'),
    }
    conn.execute(
        '''
        INSERT INTO sets (id, tcgdex_id, name, series_name, release_date, card_count_official)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          tcgdex_id=excluded.tcgdex_id,
          name=excluded.name,
          series_name=excluded.series_name,
          release_date=excluded.release_date,
          card_count_official=excluded.card_count_official
        ''',
        (
            set_row['id'],
            set_row['tcgdex_id'],
            set_row['name'],
            set_row['series_name'],
            set_row['release_date'],
            set_row['card_count_official'],
        ),
    )

    cards = data.get('cards') or []
    count = 0
    for c in cards:
        card_id = c['id'].lower().replace('-', '_')
        search_text = _search_text(set_row['name'], c['localId'], c['name'], c['id'])
        conn.execute(
            '''
            INSERT INTO cards (id, set_id, tcgdex_id, local_id, name, rarity, image_url, search_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              set_id=excluded.set_id,
              tcgdex_id=excluded.tcgdex_id,
              local_id=excluded.local_id,
              name=excluded.name,
              rarity=excluded.rarity,
              image_url=excluded.image_url,
              search_text=excluded.search_text
            ''',
            (
                card_id,
                set_row['id'],
                c['id'],
                c['localId'],
                c['name'],
                c.get('rarity'),
                c.get('image'),
                search_text,
            ),
        )
        count += 1
    return count


def import_set(
    set_id: str,
    *,
    dry_run: bool = False,
    delay_sec: float = DEFAULT_DELAY_SEC,
) -> tuple[dict[str, Any], int]:
    """Fetch one set from TCGdex and upsert into DB."""
    data = fetch_set_detail(set_id, delay_sec=delay_sec)
    cards = data.get('cards') or []
    if dry_run:
        return data, len(cards)

    ensure_db()
    with connect() as conn:
        count = upsert_set_and_cards(conn, data)
    return data, count


def load_progress() -> dict[str, Any]:
    if not PROGRESS_FILE.exists():
        return {'completed_sets': [], 'failed_sets': []}
    try:
        with PROGRESS_FILE.open(encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {'completed_sets': [], 'failed_sets': []}
    data.setdefault('completed_sets', [])
    data.setdefault('failed_sets', [])
    return data


def save_progress(progress: dict[str, Any]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    progress['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    with PROGRESS_FILE.open('w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def db_stats() -> dict[str, int]:
    ensure_db()
    with connect() as conn:
        sets = conn.execute('SELECT COUNT(*) FROM sets').fetchone()[0]
        cards = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
        prices = conn.execute('SELECT COUNT(*) FROM buyback_prices').fetchone()[0]
        sets_with_cards = conn.execute(
            'SELECT COUNT(DISTINCT set_id) FROM cards'
        ).fetchone()[0]
    return {
        'sets': sets,
        'cards': cards,
        'buyback_prices': prices,
        'sets_with_cards': sets_with_cards,
    }


# 進捗ファイルと DB の不整合を検出（seed 再実行や DB 削除後に --resume が全スキップする問題）
MIN_CARDS_WHEN_MANY_SETS_DONE = 1000
MIN_CARDS_SAMPLE_ONLY = 50


def progress_db_mismatch(progress: dict[str, Any]) -> tuple[bool, str]:
    """Return (is_mismatch, reason)."""
    completed = progress.get('completed_sets') or []
    if not completed:
        return False, ''

    stats = db_stats()
    cards = stats['cards']
    sets_with_cards = stats['sets_with_cards']
    n_completed = len(completed)

    if n_completed >= 5 and cards <= MIN_CARDS_SAMPLE_ONLY:
        return True, (
            f'進捗は {n_completed} セット完了ですが DB にはカード {cards} 枚のみ'
            '（サンプル seed のみの可能性）'
        )

    if n_completed >= 20 and cards < MIN_CARDS_WHEN_MANY_SETS_DONE:
        return True, (
            f'進捗は {n_completed} セット完了ですが DB にはカード {cards} 枚のみ'
            f'（期待: {MIN_CARDS_WHEN_MANY_SETS_DONE} 枚以上）'
        )

    if n_completed >= 10 and sets_with_cards < n_completed // 2:
        return True, (
            f'進捗完了 {n_completed} セットに対し'
            f' DB には {sets_with_cards} セット分のカードのみ'
        )

    return False, ''
