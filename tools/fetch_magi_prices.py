"""Magi (magi.camp) 出品最安価格の一括取得

データソース:
  Magi は C2C マーケットプレイスであり、公開 API で「買取価格」は提供されていません。
  `/items/search.json` から **出品中（presented / trading）の最安価格** を取得し、
  参考価格として保存します（condition_note: 参考(最安出品)）。

マッチング戦略:
  1. 検索キーワード = カード名 + セット略称（例: 「ピカチュウ 151」「リーリエのピッピex SV9」）
  2. Magi items API を price_asc で取得
  3. status が presented / trading の出品のみ対象
  4. 出品名にカード名が含まれ、local_id が一致するものを優先スコアリング
  5. スコア閾値以上の最安出品を採用（該当なしは not_found）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import connect, ensure_db

sys.stdout.reconfigure(encoding='utf-8')

MAGI_SHOP_ID = 'magi'
MAGI_SEARCH_JSON = 'https://magi.camp/items/search.json'
MAGI_SEARCH_HTML = 'https://magi.camp/items/search'
PROGRESS_FILE = Path(__file__).resolve().parents[1] / 'data' / 'magi_price_fetch_progress.json'

DEFAULT_DELAY_SEC = 1.0
REQUEST_TIMEOUT = 30
USER_AGENT = 'PokecaBuybackSearch/0.1 (+local; price-reference-fetch)'

ACTIVE_STATUSES = frozenset({'presented', 'trading'})
MIN_MATCH_SCORE = 30

# セット名 → 検索用略称（Magi 上でよく使われる表記）
SET_SEARCH_HINTS: dict[str, str] = {
    'ポケモンカード151': '151',
    'バトルパートナーズ': 'SV9',
}

_card_num_in_name = re.compile(r'(\d{1,3})\s*/\s*\d{1,3}')


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
    return {
        'completed_card_ids': [],
        'failed': [],
        'stats': {'found': 0, 'not_found': 0, 'errors': 0},
        'last_run_at': None,
    }


def save_progress(progress: dict[str, Any]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    progress['last_run_at'] = _now_iso()
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def build_search_keyword(name: str, set_name: str, set_tcgdex_id: str | None, local_id: str) -> str:
    """Magi 検索用キーワードを組み立てる。"""
    hint = SET_SEARCH_HINTS.get(set_name) or (set_tcgdex_id or '')
    parts = [name.strip()]
    if hint:
        parts.append(hint)
    return ' '.join(p for p in parts if p)


def magi_search_url(keyword: str) -> str:
    return f'{MAGI_SEARCH_HTML}?forms_search_items[keyword]={quote(keyword)}'


def magi_item_url(item_id: int | str) -> str:
    return f'https://magi.camp/items/{item_id}'


def _normalize(s: str) -> str:
    return re.sub(r'\s+', '', s.lower())


def score_listing(
    item: dict[str, Any],
    *,
    card_name: str,
    local_id: str,
    set_tcgdex_id: str | None,
) -> int:
    """出品とカードの一致度（0–100）。"""
    title = item.get('name') or item.get('display_name') or ''
    norm_title = _normalize(title)
    norm_name = _normalize(card_name)
    score = 0

    if norm_name and norm_name in norm_title:
        score += 50
    elif norm_name and any(part in norm_title for part in norm_name.split() if len(part) >= 2):
        score += 25

    lid = local_id.lstrip('0') or '0'
    lid_padded = local_id.zfill(3)
    for pattern in (f'{lid_padded}/', f'{lid}/', f'-{lid_padded}', f' {lid_padded}/'):
        if pattern.lower() in title.lower():
            score += 25
            break

    m = _card_num_in_name.search(title)
    if m and m.group(1).lstrip('0') == lid:
        score += 15

    if set_tcgdex_id:
        if set_tcgdex_id.lower() in title.lower():
            score += 10

    return score


def fetch_magi_items(keyword: str, *, session: requests.Session) -> list[dict[str, Any]]:
    params = {
        'forms_search_items[keyword]': keyword,
        'forms_search_items[sort]': 'price_asc',
    }
    resp = session.get(MAGI_SEARCH_JSON, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data.get('items') or []


def pick_best_listing(
    items: list[dict[str, Any]],
    *,
    card_name: str,
    local_id: str,
    set_tcgdex_id: str | None,
    min_score: int = MIN_MATCH_SCORE,
) -> dict[str, Any] | None:
    """アクティブ出品のうち、マッチスコア閾値以上で最安の1件。"""
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for item in items:
        if item.get('status') not in ACTIVE_STATUSES:
            continue
        price = item.get('price')
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        score = score_listing(
            item,
            card_name=card_name,
            local_id=local_id,
            set_tcgdex_id=set_tcgdex_id,
        )
        if score >= min_score:
            candidates.append((score, int(price), item))

    if not candidates:
        return None

    # スコア降順 → 同点なら価格昇順
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][2]


def lookup_magi_price(
    *,
    name: str,
    set_name: str,
    set_tcgdex_id: str | None,
    local_id: str,
    session: requests.Session,
) -> dict[str, Any] | None:
    keywords: list[str] = []
    primary = build_search_keyword(name, set_name, set_tcgdex_id, local_id)
    keywords.append(primary)
    if primary != name.strip():
        keywords.append(name.strip())
    # セット略称だけでヒットしない場合、番号付きキーワードも試す
    with_num = f'{name.strip()} {local_id.zfill(3)}'
    if with_num not in keywords:
        keywords.append(with_num)

    listing = None
    used_keyword = primary
    for keyword in keywords:
        items = fetch_magi_items(keyword, session=session)
        min_score = MIN_MATCH_SCORE if keyword == primary else 65
        candidate = pick_best_listing(
            items,
            card_name=name,
            local_id=local_id,
            set_tcgdex_id=set_tcgdex_id,
            min_score=min_score,
        )
        if candidate:
            listing = candidate
            used_keyword = keyword
            break

    if not listing:
        return None
    return {
        'price_yen': int(listing['price']),
        'product_url': magi_item_url(listing['id']),
        'search_url': magi_search_url(used_keyword),
        'keyword': used_keyword,
        'listing_name': listing.get('name') or listing.get('display_name'),
        'listing_status': listing.get('status'),
    }


def upsert_magi_price(
    conn,
    *,
    card_id: str,
    price_yen: int,
    product_url: str,
    as_of_date: str,
    recorded_at: str,
) -> None:
    condition = '参考(最安出品)'
    conn.execute(
        '''
        INSERT INTO buyback_prices (card_id, shop_id, price_yen, condition_note, as_of_date, product_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id, shop_id, as_of_date) DO UPDATE SET
            price_yen = excluded.price_yen,
            condition_note = excluded.condition_note,
            product_url = excluded.product_url
        ''',
        (card_id, MAGI_SHOP_ID, price_yen, condition, as_of_date, product_url),
    )
    conn.execute(
        '''
        INSERT INTO price_history (card_id, shop_id, price_yen, recorded_at, condition_note, product_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (card_id, MAGI_SHOP_ID, price_yen, recorded_at, condition, product_url),
    )


def list_cards(conn, *, limit: int | None = None, skip_ids: set[str] | None = None) -> list[dict[str, Any]]:
    skip_ids = skip_ids or set()
    rows = conn.execute(
        '''
        SELECT c.id, c.name, c.local_id, c.tcgdex_id, s.name AS set_name, s.tcgdex_id AS set_tcgdex_id
        FROM cards c
        JOIN sets s ON s.id = c.set_id
        ORDER BY s.release_date DESC, CAST(c.local_id AS INTEGER), c.name
        '''
    ).fetchall()
    cards = [dict(r) for r in rows if r['id'] not in skip_ids]
    if limit is not None:
        cards = cards[:limit]
    return cards


def run_fetch(
    *,
    resume: bool = False,
    force: bool = False,
    delay_sec: float = DEFAULT_DELAY_SEC,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    ensure_db()
    as_of = date.today().isoformat()
    recorded_at = _now_iso()

    progress = {'completed_card_ids': [], 'failed': [], 'stats': {'found': 0, 'not_found': 0, 'errors': 0}} if force else load_progress()
    completed: set[str] = set() if force else set(progress.get('completed_card_ids') or [])

    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})

    with connect() as conn:
        cards = list_cards(conn, limit=limit, skip_ids=completed if resume else set())
        total = len(cards)
        if resume and completed:
            print(f'再開モード: 完了済み {len(completed)} 枚をスキップ、残り {total} 枚')

        found = 0
        not_found = 0
        errors = 0

        for index, card in enumerate(cards, start=1):
            cid = card['id']
            label = f'{card["name"]} ({card["set_name"]} {card["local_id"]})'
            try:
                result = lookup_magi_price(
                    name=card['name'],
                    set_name=card['set_name'],
                    set_tcgdex_id=card.get('set_tcgdex_id'),
                    local_id=card['local_id'],
                    session=session,
                )
                if result:
                    found += 1
                    print(f'[{index}/{total}] OK  ¥{result["price_yen"]:,}  {label}')
                    if not dry_run:
                        upsert_magi_price(
                            conn,
                            card_id=cid,
                            price_yen=result['price_yen'],
                            product_url=result['product_url'],
                            as_of_date=as_of,
                            recorded_at=recorded_at,
                        )
                else:
                    not_found += 1
                    print(f'[{index}/{total}] —   該当なし  {label}')

                if not dry_run:
                    completed.add(cid)
                    progress['completed_card_ids'] = sorted(completed)
                    progress['stats'] = {'found': found, 'not_found': not_found, 'errors': errors}
                    if index % 10 == 0:
                        save_progress(progress)

            except Exception as exc:
                errors += 1
                print(f'[{index}/{total}] ERR {label}: {exc}')
                progress.setdefault('failed', []).append({'card_id': cid, 'error': str(exc)})

            if index < total:
                time.sleep(delay_sec)

        if not dry_run:
            progress['stats'] = {'found': found, 'not_found': not_found, 'errors': errors}
            save_progress(progress)

    return {'found': found, 'not_found': not_found, 'errors': errors, 'total': total}


def main() -> None:
    parser = argparse.ArgumentParser(description='Magi 参考価格（最安出品）の一括取得')
    parser.add_argument('--resume', action='store_true', help='進捗ファイルから再開')
    parser.add_argument('--force', action='store_true', help='進捗をリセットして最初から')
    parser.add_argument('--limit', type=int, default=None, help='取得枚数上限（テスト用）')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY_SEC, help=f'リクエスト間隔秒（既定 {DEFAULT_DELAY_SEC}）')
    parser.add_argument('--dry-run', action='store_true', help='API のみ叩き DB に書かない')
    args = parser.parse_args()

    with connect() as conn:
        card_count = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
    print(f'Magi 参考価格取得 — 対象カード {card_count} 枚')
    print(f'データソース: {MAGI_SEARCH_JSON}（出品最安 / 買取価格ではありません）')
    est_min = card_count * args.delay / 60
    print(f'推定所要時間: 約 {est_min:.0f} 分（間隔 {args.delay} 秒/枚）')
    if args.limit:
        print(f'テストモード: 最大 {args.limit} 枚')
    print()

    stats = run_fetch(
        resume=args.resume,
        force=args.force,
        delay_sec=args.delay,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print()
    print(f'完了: 取得成功 {stats["found"]} / 該当なし {stats["not_found"]} / エラー {stats["errors"]} / 処理 {stats["total"]} 枚')
    if not args.dry_run:
        print(f'進捗ファイル: {PROGRESS_FILE}')


if __name__ == '__main__':
    main()
