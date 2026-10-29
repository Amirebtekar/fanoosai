import re

_BODY_LIMIT = 800
_REDACTED = "[REDACTED]"
_RETRYABLE_STATUSES = {408, 425, 429}

_SK_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}")
_QUERY_RE = re.compile(r"(https?://[^\s?]+)\?\S*")


def _configured_secrets() -> list[str]:
    try:
        from app.core.config import settings
    except Exception:
        return []
    secrets = []
    for attr in ("AI_GATEWAY_API_KEY", "AVALAI_API_KEY"):
        value = getattr(settings, attr, None)
        if isinstance(value, str) and len(value) >= 8:
            secrets.append(value)
    return secrets


def coerce_body(body) -> str:
    if body is None:
        return ""
    if isinstance(body, (bytes, bytearray)):
        return bytes(body).decode("utf-8", errors="replace")
    return str(body)


def sanitize_body(body: str) -> str:
    if not body:
        return body
    sanitized = _SK_KEY_RE.sub(_REDACTED, body)
    sanitized = _BEARER_RE.sub(lambda m: m.group(0).split()[0] + " " + _REDACTED, sanitized)
    for secret in _configured_secrets():
        sanitized = sanitized.replace(secret, _REDACTED)
    return sanitized


class AIProviderError(ValueError):
    def __init__(
        self,
        provider: str,
        status: int | None,
        body: str = "",
        cause: Exception | None = None,
        primary_error: "AIProviderError | None" = None,
        fallback_error: "AIProviderError | None" = None,
        synthetic: bool = False,
    ):
        self._provider = provider
        self._status = status
        self.body = sanitize_body(coerce_body(body))[:_BODY_LIMIT]
        self.cause = cause
        self.primary_error = primary_error
        self.fallback_error = fallback_error
        self.synthetic = synthetic
        self.retry_after_seconds: int | None = None
        self._retryable_override: bool | None = None
        super().__init__(str(self))

    @property
    def effective_error(self) -> "AIProviderError | None":
        if self.fallback_error is not None and not self.fallback_error.synthetic:
            return self.fallback_error
        return self.primary_error

    @property
    def provider(self) -> str:
        eff = self.effective_error
        return eff._provider if eff is not None else self._provider

    @property
    def status(self) -> int | None:
        eff = self.effective_error
        return eff._status if eff is not None else self._status

    @property
    def retryable(self) -> bool:
        if self._retryable_override is not None:
            return self._retryable_override
        errors = [e for e in (self.primary_error, self.fallback_error) if e is not None and not e.synthetic]
        if not errors:
            s = self._status
            return s is None or s in _RETRYABLE_STATUSES or s >= 500
        return all(e.retryable for e in errors)

    @retryable.setter
    def retryable(self, value: bool) -> None:
        self._retryable_override = value

    def __str__(self) -> str:
        if self.primary_error is not None or self.fallback_error is not None:
            return self.body
        if self._status is None:
            if self.cause is not None:
                cause_name = type(self.cause).__name__
                cause_msg = sanitize_body(_QUERY_RE.sub(r"\1", str(self.cause)))
                return f"{self._provider} request failed: {cause_name}: {cause_msg}"
            return f"{self._provider} request failed: {self.body}"
        return f"{self._provider} HTTP {self._status}: {self.body}"
