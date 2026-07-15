"""
Runnable check for Swagger HTTPBearer security scheme.
Run with: python backend/tests/test_openapi_httpbearer.py
"""

import sys

sys.path.insert(0, ".")

from app.main import app


def main() -> None:
    schema = app.openapi()
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    bearer = security_schemes.get("HTTPBearer")

    assert bearer is not None, "HTTPBearer security scheme is missing from OpenAPI"
    assert bearer.get("type") == "http"
    assert bearer.get("scheme") == "bearer"
    assert bearer.get("bearerFormat") == "JWT"
    assert "OAuth2PasswordBearer" not in security_schemes

    protected_operations = [
        operation
        for path in schema["paths"].values()
        for operation in path.values()
        if operation.get("security")
    ]
    assert protected_operations, "No protected Swagger operations found"
    assert all("HTTPBearer" in operation["security"][0] for operation in protected_operations)
    print("PASS: protected Swagger operations use HTTPBearer")


if __name__ == "__main__":
    main()
