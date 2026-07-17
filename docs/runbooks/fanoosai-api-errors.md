# FanoosAI API errors

1. Check `fanoosai_http_requests_total` by route and status class.
2. Check `/health/ready` for PostgreSQL and Redis state.
3. Inspect structured logs by `request_id`.
4. If the database is saturated, reduce worker/API concurrency before increasing the pool.
