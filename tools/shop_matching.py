"""Shared card ↔ listing matching helpers."""
from __future__ import annotations

import re
from typing import Any

_card_num_in_name = re.compile(r'(\d{1,3})\s*/\s*\d{1,3}')
_card_label_re = re.compile(
    r'^(?:【[^】]+】)+(.+?)\((\d{1,3})/\d+\)([A-Za-z0-9]+)$',
)


def normalize_text(s: str) -> str:
    return re.sub(r'\s+', '', s.lower())


def parse_listing_label(label: str) -> dict[str, str] | None:
    """FullComp / 買取表の1行ラベル（例: 【RR】リーリエのピッピex(033/100)sv9）を分解。"""
    text = label.strip()
    m = _card_label_re.match(text)
    if not m:
        return None
    return {
        'name': m.group(1).strip(),
        'local_id': m.group(2).zfill(3),
        'set_code': m.group(3).upper(),
    }


def score_listing(
    listing: dict[str, Any],
    *,
    card_name: str,
    local_id: str,
    set_tcgdex_id: str | None,
    min_score: int = 30,
) -> int:
    """出品・買取行とカードの一致度（0–100）。"""
    title = listing.get('title') or listing.get('name') or listing.get('listing_name') or ''
    parsed = listing.get('parsed') or parse_listing_label(title)

    if parsed and set_tcgdex_id:
        if parsed['set_code'].upper() != set_tcgdex_id.upper():
            return 0
        if parsed['local_id'].zfill(3) != local_id.zfill(3):
            return 0

    norm_title = normalize_text(title)
    norm_name = normalize_text(card_name)
    score = 0

    if norm_name and norm_name in norm_title:
        score += 50
    elif norm_name and any(part in norm_title for part in norm_name.split() if len(part) >= 2):
        score += 25

    if parsed:
        score += 35
    else:
        lid = local_id.lstrip('0') or '0'
        lid_padded = local_id.zfill(3)
        for pattern in (f'{lid_padded}/', f'{lid}/', f'-{lid_padded}', f' {lid_padded}/'):
            if pattern.lower() in title.lower():
                score += 20
                break

        m = _card_num_in_name.search(title)
        if m and m.group(1).lstrip('0') == lid:
            score += 10

        if set_tcgdex_id and set_tcgdex_id.lower() in title.lower():
            score += 10

    return score


def pick_best_match(
    listings: list[dict[str, Any]],
    *,
    card_name: str,
    local_id: str,
    set_tcgdex_id: str | None,
    min_score: int = 70,
) -> dict[str, Any] | None:
    """スコア閾値以上で最高スコアの1件。同点なら価格降順（買取）。"""
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for item in listings:
        score = score_listing(
            item,
            card_name=card_name,
            local_id=local_id,
            set_tcgdex_id=set_tcgdex_id,
            min_score=0,
        )
        if score >= min_score:
            price = int(item.get('price_yen') or 0)
            candidates.append((score, price, item))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], -x[1]))
    return candidates[0][2]
