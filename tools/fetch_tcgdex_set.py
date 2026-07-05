"""TCGdex API から1セット分のカードマスタを取得してDBに投入（動作確認用）"""

import argparse

import sys

from pathlib import Path



sys.path.insert(0, str(Path(__file__).resolve().parents[1]))



from tools.tcgdex_import import import_set



sys.stdout.reconfigure(encoding='utf-8')





def main():

    parser = argparse.ArgumentParser(description='TCGdex からセットをインポート')

    parser.add_argument('set_id', nargs='?', default='SV9', help='TCGdex セットID（例: SV9, SV2a）')

    parser.add_argument('--dry-run', action='store_true', help='取得のみ（DB書き込みなし）')

    args = parser.parse_args()



    data, count = import_set(args.set_id.upper(), dry_run=args.dry_run)

    print(f"セット: {data['name']} ({data['id']}) — カード {count} 枚")



    if args.dry_run:

        for c in (data.get('cards') or [])[:5]:

            print(f"  - {c['localId']} {c['name']}")

        if count > 5:

            print(f"  ... 他 {count - 5} 枚")

    else:

        print(f'インポート完了: {count} 枚')





if __name__ == '__main__':

    main()

