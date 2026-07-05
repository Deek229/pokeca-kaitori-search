"""
ポケカ買取価格サーチ

起動:
  cd 13_ポケカ買取価格サーチ
  python tools/seed.py              # 初回のみ
  python -m uvicorn app:app --reload --port 8053
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from card_service import count_search_cards, get_card, list_sets, popular_cards, resolve_set_id, search_cards
from config import APP_TAGLINE, APP_TITLE, APP_VERSION, DEFAULT_PORT, SITE_URL
from templates_env import render

app = FastAPI(title=APP_TITLE, version=APP_VERSION)
ROOT = Path(__file__).parent
STATIC = ROOT / 'static'


class NoCacheHtmlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.headers.get('content-type', '').startswith('text/html'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
        return response


app.add_middleware(NoCacheHtmlMiddleware)
app.mount('/static', StaticFiles(directory=STATIC), name='static')


@app.get('/', response_class=HTMLResponse)
def home():
    return HTMLResponse(render(
        'index.html',
        app_title=APP_TITLE,
        tagline=APP_TAGLINE,
        sets=list_sets(),
        popular_cards=popular_cards(),
        site_url=SITE_URL,
    ))


DEFAULT_PAGE_SIZE = 50


@app.get('/search', response_class=HTMLResponse)
def search_page(
    q: str | None = Query(None),
    set_id: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    q_norm = (q or '').strip()
    set_id = resolve_set_id(set_id)
    has_query = bool(q_norm or set_id)
    page_size: int | None = DEFAULT_PAGE_SIZE
    if set_id and not q_norm:
        page_size = None
        page = 1

    total = count_search_cards(q=q_norm or None, set_id=set_id) if has_query else 0
    offset = 0 if page_size is None else (page - 1) * page_size
    results = (
        search_cards(q=q_norm or None, set_id=set_id, limit=page_size, offset=offset)
        if has_query
        else []
    )
    total_pages = 1 if page_size is None else max(1, (total + page_size - 1) // page_size)

    return HTMLResponse(render(
        'search.html',
        app_title=APP_TITLE,
        tagline=APP_TAGLINE,
        q=q_norm,
        set_id=set_id or '',
        sets=list_sets(),
        results=results,
        total=total,
        page=page,
        total_pages=total_pages,
        has_pagination=page_size is not None and total_pages > 1,
        site_url=SITE_URL,
    ))


@app.get('/cards/{card_id}', response_class=HTMLResponse)
def card_page(card_id: str):
    card = get_card(card_id)
    if not card:
        raise HTTPException(404, 'カードが見つかりません')
    return HTMLResponse(render(
        'card.html',
        app_title=APP_TITLE,
        card=card,
        page_title=f'{card["name"]}（{card["set_name"]}）｜{APP_TITLE}',
        site_url=SITE_URL,
    ))


@app.get('/api/cards')
def api_search_cards(
    q: str | None = None,
    set_id: str | None = None,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    page: int | None = Query(None, ge=1),
):
    q_norm = (q or '').strip() or None
    set_id = resolve_set_id(set_id)
    effective_limit = limit
    effective_offset = offset
    if set_id and not q_norm:
        effective_limit = None
        effective_offset = 0
    elif page is not None:
        page_size = effective_limit or DEFAULT_PAGE_SIZE
        effective_limit = page_size
        effective_offset = (page - 1) * page_size

    items = search_cards(
        q=q_norm,
        set_id=set_id,
        limit=effective_limit,
        offset=effective_offset,
    )
    total = count_search_cards(q=q_norm, set_id=set_id)
    return {
        'items': items,
        'total': total,
        'limit': effective_limit,
        'offset': effective_offset,
    }


@app.get('/api/cards/{card_id}')
def api_card(card_id: str):
    card = get_card(card_id)
    if not card:
        raise HTTPException(404)
    return card


@app.get('/api/sets')
def api_sets():
    return {'items': list_sets()}


@app.get('/api/health')
def health():
    return {'status': 'ok', 'app': APP_TITLE, 'version': APP_VERSION, 'port': DEFAULT_PORT}


@app.head('/api/health', include_in_schema=False)
def health_head():
    return Response(status_code=200)
