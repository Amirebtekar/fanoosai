"""Probe every ParsPack model and write a Markdown health report."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import aiohttp

from app.core.config import settings


def _one_line(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")[:160]


def model_ids(payload: dict) -> list[str]:
    models = sorted({item["id"] for item in payload.get("data", []) if item.get("id")})
    if not models:
        raise ValueError("ParsPack returned no models")
    return models


def format_report(results: list[dict]) -> str:
    successful = sum(row["active"] for row in results)
    lines = [
        "# ParsPack model health report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "| Model | Active | HTTP | Seconds | Detail |",
        "|---|---:|---:|---:|---|",
    ]
    lines.extend(
        f"| {row['model']} | {'YES' if row['active'] else 'NO'} | {row['status']} | "
        f"{row['seconds']:.2f} | {_one_line(row['detail'])} |"
        for row in results
    )
    lines.extend(["", f"**Summary:** {successful}/{len(results)} models responded successfully."])
    return "\n".join(lines) + "\n"


async def probe_model(session: aiohttp.ClientSession, url: str, model: str) -> dict:
    started = perf_counter()
    try:
        async with session.post(url, json={
            "model": model,
            "input": "Reply with exactly OK.",
            "tools": [{"type": "web_search"}],
            "tool_choice": "auto",
            "include": ["web_search_call.action.sources"],
            "max_output_tokens": 32,
        }) as response:
            body = await response.text()
            return {
                "model": model,
                "active": 200 <= response.status < 300 and bool(body.strip()),
                "status": response.status,
                "seconds": perf_counter() - started,
                "detail": body,
            }
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        return {
            "model": model,
            "active": False,
            "status": "-",
            "seconds": perf_counter() - started,
            "detail": f"{type(exc).__name__}: {exc}",
        }


async def main() -> int:
    if not settings.AI_GATEWAY_API_KEY:
        raise RuntimeError("AI_GATEWAY_API_KEY is not configured")

    base_url = settings.AI_GATEWAY_BASE_URL.rstrip("/") + "/v1"
    headers = {"Authorization": f"Bearer {settings.AI_GATEWAY_API_KEY}", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=60, connect=10)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(f"{base_url}/models") as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"ParsPack model listing failed with HTTP {response.status}")
        models = model_ids(payload)
        print(f"Testing {len(models)} ParsPack models...", flush=True)
        results = []
        for offset in range(0, len(models), 5):
            batch = await asyncio.gather(*(
                probe_model(session, f"{base_url}/responses", model)
                for model in models[offset:offset + 5]
            ))
            results.extend(batch)
            for position, row in enumerate(batch, start=len(results) - len(batch) + 1):
                print(
                    f"[{position}/{len(models)}] {row['model']}: "
                    f"{'YES' if row['active'] else 'NO'} ({row['seconds']:.2f}s)",
                    flush=True,
                )
            Path("parspack-model-report.md").write_text(
                format_report(sorted(results, key=lambda row: row["model"])), encoding="utf-8",
            )

    results.sort(key=lambda row: row["model"])
    report = format_report(results)
    print(report)
    return 0 if all(row["active"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
