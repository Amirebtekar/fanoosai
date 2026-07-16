"""
Runnable check for Swagger cookie security scheme.
Run with: python backend/tests/test_openapi_httpbearer.py
"""

import sys

sys.path.insert(0, ".")

from app.main import app


def main() -> None:
    schema = app.openapi()
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    bearer = security_schemes.get("APIKeyCookie")

    assert bearer is not None, "APIKeyCookie security scheme is missing from OpenAPI"
    assert bearer.get("type") == "apiKey"
    assert bearer.get("in") == "cookie"
    assert bearer.get("name") == "access_token"

    protected_operations = [
        operation
        for path in schema["paths"].values()
        for operation in path.values()
        if operation.get("security")
    ]
    assert protected_operations, "No protected Swagger operations found"
    assert all("APIKeyCookie" in operation["security"][0] for operation in protected_operations)
    print("PASS: protected Swagger operations use APIKeyCookie")


if __name__ == "__main__":
    main()
