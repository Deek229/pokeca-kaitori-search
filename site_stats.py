"""Server-side page view counter (data/site_stats.json)."""
import json
import re
import threading
from pathlib import Path

ROOT = Path(__file__).parent
STATS_PATH = ROOT / 'data' / 'site_stats.json'
_lock = threading.Lock()

_BOT_RE = re.compile(
    r'bot|crawler|spider|slurp|uptime|pingdom|headless|wget|curl/|python-requests|scrapy|'
    r'facebookexternalhit|mediapartners|googlebot|bingpreview|yandex',
    re.I,
)

_SKIP_PREFIXES = ('/api/', '/static/')
_SKIP_PATHS = frozenset({'/sitemap.xml', '/robots.txt', '/feed.xml', '/api/health'})


def is_bot(user_agent: str | None) -> bool:
    if not user_agent:
        return False
    return bool(_BOT_RE.search(user_agent))


def should_count_page_view(method: str, path: str, user_agent: str | None) -> bool:
    if method != 'GET':
        return False
    if path in _SKIP_PATHS or path.startswith(_SKIP_PREFIXES):
        return False
    return not is_bot(user_agent)


def get_total() -> int:
    with _lock:
        if not STATS_PATH.exists():
            return 0
        try:
            data = json.loads(STATS_PATH.read_text(encoding='utf-8'))
            return int(data.get('total', 0))
        except (json.JSONDecodeError, ValueError, OSError):
            return 0


def increment() -> int:
    with _lock:
        STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        if STATS_PATH.exists():
            try:
                data = json.loads(STATS_PATH.read_text(encoding='utf-8'))
                total = int(data.get('total', 0))
            except (json.JSONDecodeError, ValueError, OSError):
                total = 0
        total += 1
        STATS_PATH.write_text(
            json.dumps({'total': total}, ensure_ascii=False),
            encoding='utf-8',
        )
        return total
