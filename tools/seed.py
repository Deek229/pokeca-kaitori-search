"""サンプルカード・買取価格の初期投入"""
import argparse
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import connect, ensure_db

sys.stdout.reconfigure(encoding='utf-8')

AS_OF = date.today().isoformat()

SHOPS = [
    ('cardrush', 'カードラッシュ', 'cardrush', 'https://www.cardrush-pokemon.jp/'),
    ('mercard', 'メルカード', 'mercard', 'https://www.mercardpokemon.jp/'),
    ('fullcomp', 'フルコンプ', 'fullcomp', 'https://fullcomp.jp/'),
    ('magi', 'Magi', 'magi', 'https://magi.camp/'),
]

SETS = [
    {
        'id': 'sv9',
        'tcgdex_id': 'SV9',
        'name': 'バトルパートナーズ',
        'series_name': 'スカーレット&バイオレット',
        'release_date': '2025-01-24',
        'card_count_official': 100,
    },
    {
        'id': 'sv2a',
        'tcgdex_id': 'SV2a',
        'name': 'ポケモンカード151',
        'series_name': 'スカーレット&バイオレット',
        'release_date': '2023-06-16',
        'card_count_official': 165,
    },
]

# (set_id, tcgdex_id, local_id, name, rarity, image_url)
CARDS = [
    ('sv9', 'SV9-033', '033', 'リーリエのピッピex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV9/033'),
    ('sv9', 'SV9-061', '061', 'Nのゾロアークex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV9/061'),
    ('sv9', 'SV9-069', '069', 'ホップのザシアンex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV9/069'),
    ('sv9', 'SV9-030', '030', 'ナンジャモのハラバリーex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV9/030'),
    ('sv9', 'SV9-017', '017', 'ボルケニオンex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV9/017'),
    ('sv9', 'SV9-001', '001', 'キャタピー', 'Common', 'https://assets.tcgdex.net/ja/SV/SV9/001'),
    ('sv9', 'SV9-010', '010', 'ニャオハ', 'Common', 'https://assets.tcgdex.net/ja/SV/SV9/010'),
    ('sv9', 'SV9-012', '012', 'マスカーニャ', 'Rare', 'https://assets.tcgdex.net/ja/SV/SV9/012'),
    ('sv2a', 'SV2a-025', '025', 'ピカチュウ', 'Common', 'https://assets.tcgdex.net/ja/SV/SV2a/025'),
    ('sv2a', 'SV2a-173', '173', 'ピカチュウ', 'Art Rare', 'https://assets.tcgdex.net/ja/SV/SV2a/173'),
    ('sv2a', 'SV2a-001', '001', 'フシギダネ', 'Common', 'https://assets.tcgdex.net/ja/SV/SV2a/001'),
    ('sv2a', 'SV2a-006', '006', 'リザードンex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV2a/006'),
    ('sv2a', 'SV2a-150', '150', 'ミュウex', 'Double Rare', 'https://assets.tcgdex.net/ja/SV/SV2a/150'),
    ('sv2a', 'SV2a-151', '151', 'ミュウ', 'Art Rare', 'https://assets.tcgdex.net/ja/SV/SV2a/151'),
    ('sv2a', 'SV2a-134', '134', 'イーブイ', 'Common', 'https://assets.tcgdex.net/ja/SV/SV2a/134'),
]


def _magi_search_url(keyword: str) -> str:
    return f'https://magi.camp/items/search?forms_search_items[keyword]={quote(keyword)}'


# card tcgdex_id -> { shop_slug: (price_yen, condition, url) }
PRICES = {
    'SV9-033': {
        'cardrush': (8500, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (8200, '美品', 'https://mercard.jp/search?q=リーリエのピッピex'),
        'fullcomp': (8800, '美品', 'https://fullcomp.jp/search?q=リーリエのピッピex'),
        'magi': (8400, '美品', _magi_search_url('リーリエのピッピex')),
    },
    'SV9-061': {
        'cardrush': (4200, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (4000, '美品', 'https://mercard.jp/search?q=Nのゾロアークex'),
        'fullcomp': (4500, '美品', 'https://fullcomp.jp/search?q=Nのゾロアークex'),
        'magi': (4100, '美品', _magi_search_url('Nのゾロアークex')),
    },
    'SV9-069': {
        'cardrush': (12000, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (11500, '美品', 'https://mercard.jp/search?q=ホップのザシアンex'),
        'fullcomp': (11800, '美品', 'https://fullcomp.jp/search?q=ホップのザシアンex'),
        'magi': (11600, '美品', _magi_search_url('ホップのザシアンex')),
    },
    'SV9-030': {
        'cardrush': (2800, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (2600, '美品', 'https://mercard.jp/search?q=ナンジャモのハラバリーex'),
        'fullcomp': (2900, '美品', 'https://fullcomp.jp/search?q=ナンジャモのハラバリーex'),
        'magi': (2700, '美品', _magi_search_url('ナンジャモのハラバリーex')),
    },
    'SV9-017': {
        'cardrush': (350, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (320, '美品', 'https://mercard.jp/search?q=ボルケニオンex'),
        'fullcomp': (380, '美品', 'https://fullcomp.jp/search?q=ボルケニオンex'),
        'magi': (340, '美品', _magi_search_url('ボルケニオンex')),
    },
    'SV9-001': {
        'cardrush': (10, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (10, '美品', 'https://mercard.jp/search?q=キャタピー'),
        'fullcomp': (10, '美品', 'https://fullcomp.jp/search?q=キャタピー'),
        'magi': (10, '美品', _magi_search_url('キャタピー')),
    },
    'SV9-010': {
        'cardrush': (30, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (25, '美品', 'https://mercard.jp/search?q=ニャオハ'),
        'fullcomp': (30, '美品', 'https://fullcomp.jp/search?q=ニャオハ'),
        'magi': (28, '美品', _magi_search_url('ニャオハ')),
    },
    'SV9-012': {
        'cardrush': (120, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (110, '美品', 'https://mercard.jp/search?q=マスカーニャ'),
        'fullcomp': (130, '美品', 'https://fullcomp.jp/search?q=マスカーニャ'),
        'magi': (115, '美品', _magi_search_url('マスカーニャ')),
    },
    'SV2a-025': {
        'cardrush': (80, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (70, '美品', 'https://mercard.jp/search?q=ピカチュウ+151'),
        'fullcomp': (85, '美品', 'https://fullcomp.jp/search?q=ピカチュウ+151'),
        'magi': (75, '美品', _magi_search_url('ピカチュウ 151')),
    },
    'SV2a-173': {
        'cardrush': (4500, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (4200, '美品', 'https://mercard.jp/search?q=ピカチュウ+AR+151'),
        'fullcomp': (4800, '美品', 'https://fullcomp.jp/search?q=ピカチュウ+AR+151'),
        'magi': (4400, '美品', _magi_search_url('ピカチュウ AR 151')),
    },
    'SV2a-001': {
        'cardrush': (20, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (15, '美品', 'https://mercard.jp/search?q=フシギダネ'),
        'fullcomp': (20, '美品', 'https://fullcomp.jp/search?q=フシギダネ'),
        'magi': (18, '美品', _magi_search_url('フシギダネ')),
    },
    'SV2a-006': {
        'cardrush': (1800, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (1700, '美品', 'https://mercard.jp/search?q=リザードンex+151'),
        'fullcomp': (1900, '美品', 'https://fullcomp.jp/search?q=リザードンex+151'),
        'magi': (1750, '美品', _magi_search_url('リザードンex 151')),
    },
    'SV2a-150': {
        'cardrush': (2200, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (2100, '美品', 'https://mercard.jp/search?q=ミュウex+151'),
        'fullcomp': (2300, '美品', 'https://fullcomp.jp/search?q=ミュウex+151'),
        'magi': (2150, '美品', _magi_search_url('ミュウex 151')),
    },
    'SV2a-151': {
        'cardrush': (3500, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (3300, '美品', 'https://mercard.jp/search?q=ミュウ+151'),
        'fullcomp': (3600, '美品', 'https://fullcomp.jp/search?q=ミュウ+151'),
        'magi': (3400, '美品', _magi_search_url('ミュウ 151')),
    },
    'SV2a-134': {
        'cardrush': (50, '美品', 'https://www.cardrush-pokemon.jp/product/XXXX'),
        'mercard': (45, '美品', 'https://mercard.jp/search?q=イーブイ+151'),
        'fullcomp': (55, '美品', 'https://fullcomp.jp/search?q=イーブイ+151'),
        'magi': (48, '美品', _magi_search_url('イーブイ 151')),
    },
}


def _search_text(set_name: str, local_id: str, name: str, tcgdex_id: str) -> str:
    return f'{name} {set_name} {local_id} {tcgdex_id}'.lower()


def _shop_slug_to_id() -> dict[str, str]:
    return {slug: sid for sid, _, slug, _ in SHOPS}


def _upsert_shops(conn) -> int:
    added = 0
    for shop_id, name, slug, url in SHOPS:
        existing = conn.execute('SELECT id FROM shops WHERE id = ?', (shop_id,)).fetchone()
        conn.execute(
            '''
            INSERT INTO shops (id, name, slug, website_url) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                slug = excluded.slug,
                website_url = excluded.website_url
            ''',
            (shop_id, name, slug, url),
        )
        if not existing:
            added += 1
    return added


def _insert_sample_buyback_prices(conn, *, only_missing: bool) -> int:
    shop_slug_to_id = _shop_slug_to_id()
    inserted = 0
    for tcgdex_id, shop_prices in PRICES.items():
        card_id = tcgdex_id.lower().replace('-', '_')
        if not conn.execute('SELECT id FROM cards WHERE id = ?', (card_id,)).fetchone():
            continue
        for shop_slug, (price, condition, url) in shop_prices.items():
            shop_id = shop_slug_to_id[shop_slug]
            if only_missing:
                existing = conn.execute(
                    '''
                    SELECT id FROM buyback_prices
                    WHERE card_id = ? AND shop_id = ? AND as_of_date = ?
                    ''',
                    (card_id, shop_id, AS_OF),
                ).fetchone()
                if existing:
                    continue
            conn.execute(
                '''
                INSERT INTO buyback_prices (card_id, shop_id, price_yen, condition_note, as_of_date, product_url)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id, shop_id, as_of_date) DO UPDATE SET
                    price_yen = excluded.price_yen,
                    condition_note = excluded.condition_note,
                    product_url = excluded.product_url
                ''',
                (card_id, shop_id, price, condition, AS_OF, url),
            )
            inserted += 1
    return inserted


def migrate():
    """既存DBに不足ショップ・サンプル買取価格を追加（カードマスタは削除しない）"""
    ensure_db()
    with connect() as conn:
        shops_added = _upsert_shops(conn)
        prices_added = _insert_sample_buyback_prices(conn, only_missing=True)
        # Magi 表示名を「マギ」→「Magi」に統一
        conn.execute("UPDATE shops SET name = 'Magi' WHERE id = 'magi' AND name = 'マギ'")
    print(f'マイグレーション完了: 新規ショップ {shops_added} / 追加・更新した買取価格 {prices_added}')
    print(f'買取価格の更新日: {AS_OF}')


def seed():
    ensure_db()
    with connect() as conn:
        conn.execute('DELETE FROM buyback_prices')
        conn.execute('DELETE FROM cards')
        conn.execute('DELETE FROM shops')
        conn.execute('DELETE FROM sets')

        _upsert_shops(conn)

        set_names = {s['id']: s['name'] for s in SETS}
        for s in SETS:
            conn.execute(
                '''
                INSERT INTO sets (id, tcgdex_id, name, series_name, release_date, card_count_official)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (s['id'], s['tcgdex_id'], s['name'], s['series_name'], s['release_date'], s['card_count_official']),
            )

        for set_id, tcgdex_id, local_id, name, rarity, image_url in CARDS:
            card_id = tcgdex_id.lower().replace('-', '_')
            conn.execute(
                '''
                INSERT INTO cards (id, set_id, tcgdex_id, local_id, name, rarity, image_url, search_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    card_id,
                    set_id,
                    tcgdex_id,
                    local_id,
                    name,
                    rarity,
                    image_url,
                    _search_text(set_names[set_id], local_id, name, tcgdex_id),
                ),
            )

        _insert_sample_buyback_prices(conn, only_missing=False)

    print(f'シード完了: セット {len(SETS)} / カード {len(CARDS)} / ショップ {len(SHOPS)}')
    print(f'買取価格の更新日: {AS_OF}')


if __name__ == '__main__':
    from config import DB_FILE

    parser = argparse.ArgumentParser(description='サンプルデータ投入・マイグレーション')
    parser.add_argument(
        '--migrate',
        action='store_true',
        help='既存DBに不足ショップとサンプル買取価格を追加（全件削除しない）',
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='DB を全削除してサンプル15枚のみ再投入（TCGdex 取込データも消えます）',
    )
    args = parser.parse_args()

    if args.reset:
        seed()
    elif args.migrate:
        migrate()
    elif DB_FILE.exists():
        print('既存 DB を検出しました。カードマスタは削除せずマイグレーションします。')
        print('サンプル15枚だけに戻す場合: python tools\\seed.py --reset')
        migrate()
    else:
        seed()
