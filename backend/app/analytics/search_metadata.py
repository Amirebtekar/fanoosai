"""Aggregate the web-search metadata stored on ai_runs (queries and visited pages).

Values come from JSONB columns written by older and newer code paths, so every
entry is type-checked and malformed items are skipped instead of raising.
"""
from datetime import datetime
from urllib.parse import urlsplit

SITE_ACTION_TYPES = ("open_page", "find_in_page")


def normalize_query(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def safe_http_url(value) -> tuple[str, str] | None:
    """Return (url, domain) for http/https URLs with a host, else None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not host:
        return None
    return value, host


def run_search_queries(queries, actions) -> list[tuple[str, str]]:
    """Distinct (grouping key, text) queries of one run.

    Search actions are only used when the run has no usable query list.
    """
    found: dict[str, str] = {}

    def add(value) -> None:
        text = normalize_query(value)
        if text:
            found.setdefault(text.casefold(), text)

    if isinstance(queries, list):
        for value in queries:
            add(value)
    if not found and isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict) or action.get("type") != "search":
                continue
            add(action.get("query"))
            values = action.get("queries")
            if isinstance(values, list):
                for value in values:
                    add(value)
    return list(found.items())


def run_searched_sites(actions) -> list[tuple[str, str, str, str | None]]:
    """Distinct (url, domain, action_type, pattern) page actions of one run."""
    found: dict[tuple[str, str], tuple[str, str, str, str | None]] = {}
    if not isinstance(actions, list):
        return []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        if action_type not in SITE_ACTION_TYPES:
            continue
        safe = safe_http_url(action.get("url"))
        if safe is None:
            continue
        url, domain = safe
        pattern = normalize_query(action.get("pattern")) if action_type == "find_in_page" else None
        key = (url, action_type)
        if key not in found or (found[key][3] is None and pattern):
            found[key] = (url, domain, action_type, pattern)
    return list(found.values())


def _timestamp(value) -> float:
    return value.timestamp() if isinstance(value, datetime) else float("-inf")


def _newer(candidate, current) -> bool:
    return _timestamp(candidate) > _timestamp(current)


def _sort_newest_first(groups: list[dict]) -> list[dict]:
    return sorted(groups, key=lambda group: _timestamp(group["run_date"]), reverse=True)


def group_search_queries(rows) -> list[dict]:
    """Group rows of (prompt_id, prompt, ai_model_id, ai_model, run_date, queries, actions, *extra).

    ``count`` is the number of runs that used the query; the text and date come
    from the most recent run. ``extra`` keeps any trailing row values.
    """
    groups: dict[tuple, dict] = {}
    for prompt_id, prompt, model_id, model, run_date, queries, actions, *extra in rows:
        for key, text in run_search_queries(queries, actions):
            group = groups.get((key, prompt_id, model_id))
            if group is None:
                groups[(key, prompt_id, model_id)] = {
                    "query": text,
                    "prompt_id": prompt_id,
                    "prompt": prompt,
                    "ai_model_id": model_id,
                    "ai_model": model,
                    "run_date": run_date,
                    "count": 1,
                    "extra": tuple(extra),
                }
                continue
            group["count"] += 1
            if _newer(run_date, group["run_date"]):
                group.update(query=text, run_date=run_date)
    return _sort_newest_first(list(groups.values()))


def group_searched_sites(rows) -> list[dict]:
    """Group rows of (prompt_id, prompt, ai_model_id, ai_model, run_date, actions, *extra)."""
    groups: dict[tuple, dict] = {}
    for prompt_id, prompt, model_id, model, run_date, actions, *extra in rows:
        for url, domain, action_type, pattern in run_searched_sites(actions):
            group = groups.get((url, action_type, prompt_id, model_id))
            if group is None:
                groups[(url, action_type, prompt_id, model_id)] = {
                    "url": url,
                    "domain": domain,
                    "action_type": action_type,
                    "pattern": pattern,
                    "prompt_id": prompt_id,
                    "prompt": prompt,
                    "ai_model_id": model_id,
                    "ai_model": model,
                    "run_date": run_date,
                    "count": 1,
                    "extra": tuple(extra),
                }
                continue
            group["count"] += 1
            if _newer(run_date, group["run_date"]):
                group["run_date"] = run_date
                if pattern:
                    group["pattern"] = pattern
            elif group["pattern"] is None and pattern:
                group["pattern"] = pattern
    return _sort_newest_first(list(groups.values()))


def query_matches(query: str, search: str) -> bool:
    needle = normalize_query(search)
    return not needle or needle.casefold() in query.casefold()
