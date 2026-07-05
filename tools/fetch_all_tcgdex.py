"""TCGdex API から日本語セット・カードを一括インポート"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import connect, ensure_db
from tools.tcgdex_import import (
    DEFAULT_DELAY_SEC,
    MIN_CARDS_WHEN_MANY_SETS_DONE,
    PROGRESS_FILE,
    db_stats,
    fetch_all_set_summaries,
    fetch_set_detail,
    load_progress,
    progress_db_mismatch,
    save_progress,
    upsert_set_and_cards,
)

sys.stdout.reconfigure(encoding='utf-8')


def _print_stats(label: str) -> None:
    stats = db_stats()
    print(f'{label}: セット {stats["sets"]} / カード {stats["cards"]} / 買取価格 {stats["buyback_prices"]}')


def run_import(
    *,
    resume: bool = False,
    force: bool = False,
    delay_sec: float = DEFAULT_DELAY_SEC,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    started = time.time()
    progress = {'completed_sets': [], 'failed_sets': []} if force else load_progress()
    completed = set(progress.get('completed_sets') or [])
    failed: list[dict[str, str]] = []

    print('TCGdex 日本語セット一覧を取得中...')
    summaries = fetch_all_set_summaries(delay_sec=delay_sec)
    set_ids = [s['id'] for s in summaries if s.get('id')]
    if limit is not None:
        set_ids = set_ids[:limit]

    total = len(set_ids)
    skipped = 0
    imported_sets = 0
    imported_cards = 0

    print(f'対象セット: {total} 件（リクエスト間隔 {delay_sec} 秒）')
    if resume and completed:
        print(f'再開モード: 完了済み {len(completed)} セットをスキップします')
    if dry_run:
        print('ドライラン: DB には書き込みません')
    print()

    ensure_db()

    for index, set_id in enumerate(set_ids, start=1):
        if resume and set_id in completed and not force:
            skipped += 1
            continue

        try:
            data = fetch_set_detail(set_id, delay_sec=delay_sec)
            name = data.get('name', set_id)
            cards = data.get('cards') or []
            card_count = len(cards)

            if dry_run:
                print(f'[{index}/{total}] {set_id} {name} — {card_count} 枚（取得のみ）')
            else:
                with connect() as conn:
                    card_count = upsert_set_and_cards(conn, data)
                progress.setdefault('completed_sets', [])
                if set_id not in progress['completed_sets']:
                    progress['completed_sets'].append(set_id)
                progress['failed_sets'] = [
                    f for f in progress.get('failed_sets', []) if f.get('id') != set_id
                ]
                save_progress(progress)
                completed.add(set_id)
                imported_sets += 1
                imported_cards += card_count
                print(f'[{index}/{total}] {set_id} {name} — {card_count} 枚 完了（累計 {imported_cards} 枚）')

        except Exception as exc:
            err = str(exc)
            failed.append({'id': set_id, 'error': err})
            progress.setdefault('failed_sets', [])
            progress['failed_sets'] = [
                f for f in progress['failed_sets'] if f.get('id') != set_id
            ]
            progress['failed_sets'].append({'id': set_id, 'error': err})
            save_progress(progress)
            print(f'[{index}/{total}] {set_id} — 失敗: {err}', file=sys.stderr)

    elapsed = time.time() - started
    print()
    print('=' * 50)
    print(f'処理時間: {elapsed:.0f} 秒 ({elapsed / 60:.1f} 分)')
    print(f'インポート: セット {imported_sets} / カード {imported_cards}')
    if skipped:
        print(f'スキップ: {skipped} セット（再開モード）')
    if failed:
        print(f'失敗: {len(failed)} セット')
        for item in failed:
            print(f'  - {item["id"]}: {item["error"]}')
    else:
        print('失敗: なし')

    if not dry_run:
        _print_stats('DB 最終')
        print(f'進捗ファイル: {PROGRESS_FILE}')
        with connect() as conn:
            sets_with_cards = conn.execute(
                'SELECT COUNT(DISTINCT set_id) FROM cards'
            ).fetchone()[0]
            total_in_db = conn.execute('SELECT COUNT(*) FROM sets').fetchone()[0]
            meta_only = total_in_db - sets_with_cards
        if meta_only:
            print(
                f'※ カード0件のセット {meta_only} 件'
                f'（TCGdex API にカード一覧が未登録のセット）'
            )

    return {
        'total_sets': total,
        'imported_sets': imported_sets,
        'imported_cards': imported_cards,
        'skipped_sets': skipped,
        'failed_sets': failed,
        'elapsed_sec': elapsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description='TCGdex から日本語の全セット・カードを一括インポート（買取価格は投入しません）',
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='前回の進捗から再開（完了済みセットをスキップ）',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='進捗をリセットして最初から実行',
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=DEFAULT_DELAY_SEC,
        metavar='SEC',
        help=f'API リクエスト間隔（秒、既定 {DEFAULT_DELAY_SEC}）',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='取得のみ（DB 書き込みなし）',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        metavar='N',
        help='先頭 N セットだけ処理（動作確認用）',
    )
    args = parser.parse_args()

    force = args.force
    resume = args.resume and not force

    if not force and not args.dry_run:
        progress = load_progress()
        mismatch, reason = progress_db_mismatch(progress)
        if mismatch:
            print('=' * 50)
            print(' 警告: 進捗ファイルと DB が一致しません')
            print('=' * 50)
            print(reason)
            print('進捗をリセットして最初から再インポートします。')
            print('（意図的に続きから再開したい場合は --force なしで DB を復元してください）')
            print()
            if PROGRESS_FILE.exists():
                PROGRESS_FILE.unlink(missing_ok=True)
            force = True
            resume = False

    if force and PROGRESS_FILE.exists() and not args.dry_run:
        PROGRESS_FILE.unlink(missing_ok=True)

    print('=' * 50)
    print(' TCGdex 全カード取込')
    print('=' * 50)
    _print_stats('開始時')
    print()

    result = run_import(
        resume=resume or not force,
        force=force,
        delay_sec=args.delay,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    if not args.dry_run:
        final = db_stats()
        if final['cards'] < MIN_CARDS_WHEN_MANY_SETS_DONE and result['imported_cards'] == 0:
            print()
            print('[警告] カードが増えていません。--force で再実行するか seed 後に再度お試しください。')
            sys.exit(1)


if __name__ == '__main__':
    main()
