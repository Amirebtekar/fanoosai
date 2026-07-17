"""Small dependency-light HTTP load test for the three requested scenarios.

Run against a staging API only. The default endpoint is read-only liveness and
does not enqueue AI jobs.
"""

import argparse
import asyncio
import statistics
import time

import httpx


async def run_scenario(base_url: str, users: int, duration: int) -> dict[str, object]:
    deadline = time.perf_counter() + duration
    latencies: list[float] = []
    errors = 0
    requests = 0
    limits = httpx.Limits(max_connections=min(users, 1000), max_keepalive_connections=200)
    async with httpx.AsyncClient(base_url=base_url, timeout=10, limits=limits) as client:
        async def virtual_user() -> None:
            nonlocal errors, requests
            while time.perf_counter() < deadline:
                started = time.perf_counter()
                try:
                    response = await client.get("/health/live")
                    requests += 1
                    if response.status_code >= 500:
                        errors += 1
                    else:
                        latencies.append((time.perf_counter() - started) * 1000)
                except httpx.HTTPError:
                    requests += 1
                    errors += 1

        await asyncio.gather(*(virtual_user() for _ in range(users)))

    sorted_latencies = sorted(latencies)
    percentile = lambda p: sorted_latencies[min(int(len(sorted_latencies) * p), len(sorted_latencies) - 1)] if sorted_latencies else None
    return {
        "users": users,
        "duration_seconds": duration,
        "requests": requests,
        "errors": errors,
        "error_rate": round(errors / requests, 4) if requests else None,
        "p50_ms": round(percentile(0.50), 2) if percentile(0.50) is not None else None,
        "p95_ms": round(percentile(0.95), 2) if percentile(0.95) is not None else None,
        "p99_ms": round(percentile(0.99), 2) if percentile(0.99) is not None else None,
        "mean_ms": round(statistics.mean(latencies), 2) if latencies else None,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--users", type=int, nargs="+", default=[100, 1000, 10000])
    args = parser.parse_args()
    for users in args.users:
        print(await run_scenario(args.base_url, users, args.duration))


if __name__ == "__main__":
    asyncio.run(main())
