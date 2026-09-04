# Background processing

The API persists notifications and jobs in the same database transaction as the
business action. Financial posting therefore remains synchronous and
transactional; no Redis or worker availability is required to post an expense
or ledger transaction.

By default `TASK_QUEUE_BACKEND=in_process` is used for local development and
tests. A separate worker should call `BackgroundWorker.run_once` or
`run_until_empty` with `default_handlers()`. Deployments that already operate
Redis can select `TASK_QUEUE_BACKEND=redis` and provide a `RedisTaskQueue`
adapter with an async Redis client. Redis is intentionally not a mandatory
dependency.

Email, report generation, scheduled reports, and cleanup are job kinds with
retry/backoff and durable idempotency keys. Configure SMTP using `EMAIL_ENABLED`,
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, and
`EMAIL_FROM`. Failed jobs are visible at `GET /api/v1/jobs` and can be retried
by an authorized administrator.
