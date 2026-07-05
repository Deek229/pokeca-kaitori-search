"""買取価格の一括取得（フルコンプ / カードラッシュ / メルカード）

使い方:
  python tools/fetch_shop_prices.py --shop all --all --refresh      # 全カード（約6143枚）
  python tools/fetch_shop_prices.py --shop fullcomp --set SV9 --refresh
  python tools/fetch_shop_prices.py --shop cardrush --all --limit 20  # テスト
  python tools/fetch_shop_prices.py --shop all --all --resume         # 同日中断のみ再開

データソース:
  - フルコンプ: 店舗買取表 HTML 内の tableData（一括取得・全店同一価格）
  - カードラッシュ: [cardrush.media](https://cardrush.media/pokemon/buying_prices) 買取表（`__NEXT_DATA__` 内 JSON・全ページ取得）
  - メルカード: mercardpokemon.jp（通販休業中で 503。`--shop all` ではスキップ・検索リンクのみ）
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import connect, ensure_db
from shop_fetch_common import (
    USER_AGENT,
    list_cards,
    load_progress,
    now_iso,
    progress_run_date,
    resume_skip_ids,
    save_progress,
    upsert_buyback_price,
)
from shop_matching import pick_best_match
from shops import cardrush, fullcomp, mercard

sys.stdout.reconfigure(encoding='utf-8')

SHOPS = {
    'fullcomp': fullcomp,
    'cardrush': cardrush,
    'mercard': mercard,
}

BULK_SHOPS = frozenset({'fullcomp', 'cardrush', 'mercard'})
# --shop all の対象（メルカードは 503 のため除外。個別 --shop mercard は可能）
ACTIVE_SHOPS = ('fullcomp', 'cardrush')
MERCARD_SKIP_MSG = (
    'メルカード: 通販サイト休業中（503）のためスキップ。'
    ' カード詳細では検索リンクのみ表示します。'
)



def _load_catalog(shop_mod, session: requests.Session) -> tuple[list[dict[str, Any]], list[str], str | None]:
    return shop_mod.load_buylist_catalog(session=session)


def _lookup_in_catalog(
    catalog: list[dict[str, Any]],
    *,
    name: str,
    local_id: str,
    set_tcgdex_id: str | None,
    shop_mod,
) -> dict[str, Any] | None:
    match = pick_best_match(
        catalog,
        card_name=name,
        local_id=local_id,
        set_tcgdex_id=set_tcgdex_id,
        min_score=70,
    )
    if not match:
        return None
    product_url = match.get('source_url') or shop_mod.search_url_for_card(name, set_tcgdex_id)
    condition = match.get('note') or '美品'
    if condition and condition not in ('美品', '—'):
        condition = f'美品 · {condition}'
    else:
        condition = '美品'
    return {
        'price_yen': int(match['price_yen']),
        'product_url': product_url,
        'condition_note': condition,
        'listing_name': match.get('title'),
    }


def run_shop_fetch(
    shop_slug: str,
    *,
    set_tcgdex_id: str | None = None,
    resume: bool = False,
    refresh: bool = False,
    force: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
    delay_sec: float = 0.0,
) -> dict[str, Any]:
    shop_mod = SHOPS[shop_slug]
    ensure_db()
    as_of = date.today().isoformat()
    recorded_at = now_iso()

    progress = (
        {
            'completed_card_ids': [],
            'failed': [],
            'stats': {'found': 0, 'not_found': 0, 'errors': 0, 'skipped': 0},
            'as_of_date': as_of,
        }
        if force
        else load_progress(shop_slug)
    )
    if force or refresh or progress_run_date(progress) != date.today():
        completed: set[str] = set()
    else:
        completed = set(progress.get('completed_card_ids') or [])
    skip_ids = resume_skip_ids(progress, resume=resume, refresh=refresh, force=force)

    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT, 'Accept-Language': 'ja,en;q=0.9'})

    catalog: list[dict[str, Any]] = []
    catalog_sources: list[str] = []
    catalog_error: str | None = None
    catalog_usable = True

    if shop_slug in BULK_SHOPS:
        print(f'[{shop_slug}] 買取表カタログを読み込み中...')
        catalog, catalog_sources, catalog_error = _load_catalog(shop_mod, session)
        if catalog_error:
            print(f'  警告: {catalog_error}')
        print(f'  カタログ行数: {len(catalog)} / ソース: {", ".join(catalog_sources[:2])}')
        catalog_usable = bool(catalog) or not catalog_error
        if catalog_error and not catalog:
            print('  → カタログ未取得のため、カードは完了扱いにしません')
        if not dry_run:
            progress['catalog_loaded_at'] = now_iso()
            progress['catalog_sources'] = catalog_sources
            progress['catalog_error'] = catalog_error

    found = 0
    not_found = 0
    errors = 0
    skipped = len(skip_ids)

    with connect() as conn:
        cards = list_cards(
            conn,
            set_tcgdex_id=set_tcgdex_id,
            limit=limit,
            skip_ids=skip_ids,
        )
        total = len(cards)
        quiet = total > 200 and limit is None
        if skipped:
            print(f'再開: 本日完了済み {skipped} 枚スキップ、残り {total} 枚')
        elif refresh:
            print('更新: 進捗に関係なく全カードを再取得します')
        elif resume and progress_run_date(progress) != date.today():
            print('日付が変わったため、全カードを再取得します')
        if quiet:
            print(f'大量処理モード: 該当なしは省略表示（{total} 枚）。ヒット・エラー・進捗のみ表示します。')

        t0 = time.monotonic()
        log_every = max(50, total // 20) if total else 50

        for index, card in enumerate(cards, start=1):
            cid = card['id']
            label = f'{card["name"]} ({card["set_name"]} {card["local_id"]})'
            try:
                result = None
                if catalog:
                    result = _lookup_in_catalog(
                        catalog,
                        name=card['name'],
                        local_id=card['local_id'],
                        set_tcgdex_id=card.get('set_tcgdex_id'),
                        shop_mod=shop_mod,
                    )
                if result:
                    found += 1
                    print(f'[{index}/{total}] OK  ¥{result["price_yen"]:,}  {label}')
                    if not dry_run:
                        upsert_buyback_price(
                            conn,
                            card_id=cid,
                            shop_id=shop_mod.SHOP_ID,
                            price_yen=result['price_yen'],
                            condition_note=result['condition_note'],
                            as_of_date=as_of,
                            recorded_at=recorded_at,
                            product_url=result['product_url'],
                        )
                else:
                    not_found += 1
                    if not quiet:
                        print(f'[{index}/{total}] —   該当なし  {label}')

                if not dry_run and catalog_usable:
                    completed.add(cid)
                    progress['completed_card_ids'] = sorted(completed)
                    progress['stats'] = {
                        'found': found,
                        'not_found': not_found,
                        'errors': errors,
                        'skipped': skipped,
                    }
                    if index % 20 == 0:
                        save_progress(shop_slug, progress, as_of_date=as_of)

                if index % log_every == 0 or index == total:
                    elapsed = time.monotonic() - t0
                    pct = index / total * 100 if total else 0
                    rate = index / elapsed if elapsed > 0 else 0
                    eta = (total - index) / rate if rate > 0 else 0
                    print(
                        f'  …進捗 {index}/{total} ({pct:.0f}%)'
                        f' | ヒット {found} / 該当なし {not_found}'
                        f' | 経過 {elapsed:.0f}s'
                        + (f' / 残り約 {eta:.0f}s' if eta > 0 and index < total else '')
                    )

            except Exception as exc:
                errors += 1
                print(f'[{index}/{total}] ERR {label}: {exc}')
                progress.setdefault('failed', []).append({'card_id': cid, 'error': str(exc)})

            if delay_sec > 0 and index < total:
                time.sleep(delay_sec)

        if not dry_run:
            if catalog_usable:
                progress['completed_card_ids'] = sorted(completed)
            else:
                progress['completed_card_ids'] = []
            progress['stats'] = {
                'found': found,
                'not_found': not_found,
                'errors': errors,
                'skipped': skipped,
            }
            save_progress(shop_slug, progress, as_of_date=as_of)

    return {
        'shop': shop_slug,
        'found': found,
        'not_found': not_found,
        'errors': errors,
        'skipped': skipped,
        'total': total,
        'catalog_size': len(catalog),
        'catalog_error': catalog_error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='3店舗 買取価格の一括取得')
    parser.add_argument(
        '--shop',
        choices=['fullcomp', 'cardrush', 'mercard', 'all'],
        default='all',
        help='対象ショップ（既定: all）',
    )
    parser.add_argument('--set', dest='set_id', default='SV9', help='TCGdex セット ID（例: SV9）。--all のとき無視')
    parser.add_argument('--all', action='store_true', help='全カード対象（--set を無効化）')
    parser.add_argument(
        '--resume',
        action='store_true',
        help='同日の中断分のみ再開（本日完了済みカードをスキップ）',
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='進捗の完了状態に関係なく全カードを再取得（日次更新向け・既定）',
    )
    parser.add_argument('--force', action='store_true', help='進捗ファイルをリセットして最初から')
    parser.add_argument('--limit', type=int, default=None, help='取得枚数上限（テスト用）')
    parser.add_argument('--delay', type=float, default=0.0, help='カード間隔秒（通常 0 で一括マッチ）')
    parser.add_argument('--dry-run', action='store_true', help='DB に書かない')
    args = parser.parse_args()

    set_filter = None if args.all else (args.set_id or 'SV9').upper()
    if args.shop == 'all':
        shops = list(ACTIVE_SHOPS)
    else:
        shops = [args.shop]

    with connect() as conn:
        if set_filter:
            n = conn.execute(
                '''
                SELECT COUNT(*) FROM cards c JOIN sets s ON s.id = c.set_id
                WHERE s.tcgdex_id = ?
                ''',
                (set_filter,),
            ).fetchone()[0]
            scope = f'セット {set_filter}（{n} 枚）'
        else:
            n = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
            scope = f'全カード（{n} 枚）'

    print(f'買取価格取得 — {scope}')
    print(f'対象ショップ: {", ".join(shops)}')
    if args.shop == 'all':
        print(f'  ※ {MERCARD_SKIP_MSG}')
    if args.limit:
        print(f'テストモード: 最大 {args.limit} 枚')
    if args.dry_run:
        print('ドライラン: DB には書き込みません')
    print()

    summaries: list[dict[str, Any]] = []
    for shop_slug in shops:
        print(f'=== {shop_slug} ===')
        stats = run_shop_fetch(
            shop_slug,
            set_tcgdex_id=set_filter,
            resume=args.resume,
            refresh=args.refresh or not args.resume,
            force=args.force,
            limit=args.limit,
            dry_run=args.dry_run,
            delay_sec=args.delay,
        )
        summaries.append(stats)
        processed = stats['found'] + stats['not_found'] + stats['errors']
        rate = (stats['found'] / processed * 100) if processed else 0
        skip_part = f' / スキップ {stats["skipped"]}' if stats['skipped'] else ''
        print(
            f'完了: 更新 {stats["found"]} / 該当なし {stats["not_found"]} / エラー {stats["errors"]}'
            f'{skip_part} / 処理 {processed} 枚 ({rate:.1f}% ヒット)'
        )
        if stats.get('catalog_error'):
            print(f'  注: {stats["catalog_error"]}')
        print()

    if len(summaries) > 1:
        print('--- サマリー ---')
        for s in summaries:
            rate = (s['found'] / s['total'] * 100) if s['total'] else 0
            status = 'OK' if s['found'] else ('PARTIAL' if s.get('catalog_error') else '—')
            print(f"  {s['shop']:10} {status:8} {s['found']:4}/{s['total']} ({rate:.1f}%)  catalog={s['catalog_size']}")


if __name__ == '__main__':
    main()
