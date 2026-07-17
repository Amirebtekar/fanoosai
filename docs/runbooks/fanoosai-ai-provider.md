# FanoosAI AI provider failures

1. Check `fanoosai_ai_requests_total` and `fanoosai_ai_request_duration_seconds` by provider.
2. Check worker logs for retry exhaustion.
3. Confirm provider quota, timeout, and upstream health.
4. Pause the scheduler if the provider is returning sustained 5xx/429 responses.
