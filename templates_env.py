"""Jinja2 テンプレート環境"""
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).parent
env = Environment(
    loader=FileSystemLoader(str(ROOT / 'templates')),
    autoescape=select_autoescape(['html', 'xml']),
    auto_reload=True,
)


def _tojson(value) -> Markup:
    return Markup(json.dumps(value, ensure_ascii=False))


def _yen(value) -> str:
    if value is None:
        return '—'
    return f'¥{int(value):,}'


env.filters['tojson'] = _tojson
env.filters['yen'] = _yen


def render(template_name: str, **context) -> str:
    return env.get_template(template_name).render(**context)
