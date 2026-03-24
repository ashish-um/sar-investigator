"""
Tool: screen_watchlist

Screens a name against the internal watchlist table across three match types:
  1. Exact match on entity_name
  2. Alias match — each pipe-separated alias is checked
  3. Fuzzy match — token overlap for near-misses

Returns matched rows with computed flags: is_sanctioned, is_pep,
is_absolute_prohibition, is_overdue_review, match_type, match_confidence.
"""

import json
from datetime import date, datetime
from typing import Optional
from langchain_core.tools import tool
from tools.db import get_connection


def _parse_date(date_str: str) -> Optional[date]:
    """Try to parse a date string in common formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m-%d-%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _token_overlap(a: str, b: str) -> float:
    """Compute Jaccard-style token overlap between two strings."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _build_result(row: dict, match_type: str, match_confidence: str) -> dict:
    """Build a single match result dict from a watchlist row."""
    today = date.today()

    # Split aliases from pipe-separated string to list
    aliases_raw = row.get("aliases") or ""
    aliases_list = [a.strip() for a in aliases_raw.split("|") if a.strip()] if aliases_raw else []

    # Compute flags
    wl_type = (row.get("watchlist_type") or "").upper()
    is_sanctioned = wl_type == "SANCTIONS"
    is_pep = wl_type == "PEP"

    # Check if review is overdue
    is_overdue_review = False
    review_due = _parse_date(row.get("review_due_date") or "")
    if review_due and review_due < today:
        is_overdue_review = True

    return {
        "watchlist_id": row.get("watchlist_id"),
        "entity_name": row.get("entity_name"),
        "aliases": aliases_list,
        "entity_type": row.get("entity_type"),
        "watchlist_type": row.get("watchlist_type"),
        "source": row.get("source"),
        "listed_date": row.get("listed_date"),
        "country_of_incorporation": row.get("country_of_incorporation"),
        "country_of_operation": row.get("country_of_operation"),
        "risk_score": row.get("risk_score"),
        "status": row.get("status"),
        "last_reviewed_date": row.get("last_reviewed_date"),
        "review_due_date": row.get("review_due_date"),
        "related_entity_id": row.get("related_entity_id"),
        "notes": row.get("notes"),
        # Computed flags
        "is_sanctioned": is_sanctioned,
        "is_pep": is_pep,
        "is_absolute_prohibition": bool(row.get("is_absolute_prohibition")),
        "is_overdue_review": is_overdue_review,
        "match_type": match_type,
        "match_confidence": match_confidence,
    }


@tool
def screen_watchlist(name: str, entity_type: Optional[str] = None) -> str:
    """Screen a counterparty or entity name against the internal watchlist database.
    Checks for exact name matches, alias matches, and fuzzy (token overlap) matches.
    Call this when: (a) a counterparty name appears in transaction history,
    (b) the customer profile shows pep_flag=True or sanctions_flag=True to confirm
    the specific watchlist entry, or (c) any alias or related entity name appears
    in payment references.

    Args:
        name: The entity or counterparty name to screen.
        entity_type: Optional filter — 'INDIVIDUAL' or 'ORGANISATION'.
    """

    matches = []
    name_lower = name.strip().lower()

    with get_connection() as conn:
        # Build base query
        query = "SELECT * FROM watchlists"
        params: list = []
        if entity_type:
            query += " WHERE entity_type = ?"
            params.append(entity_type.upper())

        cursor = conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]

    # Track matched watchlist IDs to avoid duplicates
    matched_ids: set = set()

    # 1. Exact match on entity_name
    for row in rows:
        if (row.get("entity_name") or "").strip().lower() == name_lower:
            if row["watchlist_id"] not in matched_ids:
                matches.append(_build_result(row, "EXACT", "HIGH"))
                matched_ids.add(row["watchlist_id"])

    # 2. Alias match
    for row in rows:
        if row["watchlist_id"] in matched_ids:
            continue
        aliases_raw = row.get("aliases") or ""
        aliases = [a.strip().lower() for a in aliases_raw.split("|") if a.strip()]
        if name_lower in aliases:
            matches.append(_build_result(row, "ALIAS", "HIGH"))
            matched_ids.add(row["watchlist_id"])

    # 3. Fuzzy match — token overlap >= 0.5
    FUZZY_THRESHOLD = 0.5
    for row in rows:
        if row["watchlist_id"] in matched_ids:
            continue
        entity_name = (row.get("entity_name") or "").strip()
        aliases_raw = row.get("aliases") or ""
        aliases = [a.strip() for a in aliases_raw.split("|") if a.strip()]

        # Check against entity_name
        overlap = _token_overlap(name, entity_name)
        if overlap >= FUZZY_THRESHOLD:
            confidence = "MEDIUM" if overlap >= 0.6 else "LOW"
            matches.append(_build_result(row, "FUZZY", confidence))
            matched_ids.add(row["watchlist_id"])
            continue

        # Check against each alias
        for alias in aliases:
            overlap = _token_overlap(name, alias)
            if overlap >= FUZZY_THRESHOLD:
                confidence = "MEDIUM" if overlap >= 0.6 else "LOW"
                matches.append(_build_result(row, "FUZZY", confidence))
                matched_ids.add(row["watchlist_id"])
                break

    result = {
        "query": name,
        "entity_type_filter": entity_type,
        "total_matches": len(matches),
        "matches": matches,
    }

    return json.dumps(result, default=str)
