# Background processing

The application persists background jobs in `background_jobs` and delivers them
through an in-process queue for development and tests. Deployments can select
the Redis adapter with `TASK_QUEUE_BACKEND=redis`; queue failure falls back to
the local adapter while the durable job record remains authoritative.

`NotificationService` writes in-app notifications in the caller's transaction.
Email delivery, large report generation, scheduled reports, and cleanup are
worker job types. Jobs use idempotency keys and exponential retry backoff.

Financial posting remains synchronous and transactional. It does not wait for a
worker; optional notifications are durable side effects created alongside the
business transaction.

Configure Redis and SMTP through environment variables:

- `REDIS_URL`
- `TASK_QUEUE_BACKEND`
- `TASK_QUEUE_MAX_RETRIES`
- `TASK_QUEUE_RETRY_DELAY_SECONDS`
- `EMAIL_ENABLED`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`

Job payloads and notification payloads are redacted when exposed through
administration APIs. Passwords and authentication tokens must not be included
in audit details or other non-delivery payloads.
