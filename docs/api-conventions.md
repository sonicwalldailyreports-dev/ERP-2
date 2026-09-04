# API conventions

- Base path: `/api/v1`
- Health endpoint: `GET /health` (outside the versioned business API)
- JSON uses `camelCase` only if the client contract requires it; Python internals remain `snake_case`.
- Authentication will use secure, server-validated tokens and explicit tenant context.
- Authorization is enforced in dependencies/services, never only in the UI.
- Mutating endpoints must define idempotency behavior where retries could duplicate financial effects.
- Pagination, filtering, sorting, and request correlation headers will be standardized before business modules are exposed.

