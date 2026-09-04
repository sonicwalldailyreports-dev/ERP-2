# Development conventions

## Naming

Use `snake_case` for Python files, functions, variables, and database columns; `PascalCase` for Python classes and React components; `camelCase` for TypeScript variables and API properties. Use singular domain module names. Use explicit names (`CustomerRepository`) over generic managers.

## API

Use `/api/v1` versioning, plural resource paths, JSON request/response bodies, and HTTP status codes semantically. List endpoints use `items`, `total`, `limit`, and `offset`. Dates are ISO-8601 UTC values. IDs are opaque UUIDs at API boundaries. Never expose persistence-only fields.

## Errors

Expected domain failures use a stable JSON envelope:

```json
{"error": {"code": "RESOURCE_NOT_FOUND", "message": "Customer was not found.", "details": {}}}
```

Validation errors use FastAPI's standard 422 shape. Unexpected exceptions are logged with a correlation ID and return a generic 500 response without implementation details.

## Configuration

Configuration is loaded from environment variables through one typed settings object. `.env.example` documents supported values; secrets are never committed. Development defaults may use SQLite, while production requires PostgreSQL.

## Testing

Backend tests use pytest and dependency overrides. Unit tests cover services and repositories; API tests cover authorization, tenant isolation, validation, and response contracts. Frontend tests will be added with the existing toolchain when UI behavior exists. Keep tests deterministic and avoid real external services.

