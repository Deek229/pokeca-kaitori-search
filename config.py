"""13 ポケカ買取価格サーチ 設定"""
import os
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / 'data'
DB_FILE = DATA_DIR / 'cards.db'

APP_TITLE = 'ポケカ買取価格サーチ'
APP_TAGLINE = '主要ショップの買取価格をカード名・番号で横並び比較'
APP_VERSION = '0.1.0'
DEFAULT_PORT = int(os.environ.get('PORT', '8053'))
SITE_URL = os.environ.get(
    'SITE_URL',
    os.environ.get('RENDER_EXTERNAL_URL', f'http://127.0.0.1:{DEFAULT_PORT}'),
).rstrip('/')

TCGDEX_API_BASE = 'https://api.tcgdex.net/v2/ja'
TCGDEX_LANG = 'ja'
