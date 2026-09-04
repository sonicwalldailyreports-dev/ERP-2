# Expenses

Expenses are company/branch-scoped documents with the same DRAFT → SUBMITTED →
APPROVED → POSTED workflow as the Cash Book. Posted documents are immutable:
use `POST /expenses/{id}/reverse` for a compensating reversal or
`POST /expenses/{id}/adjust` to create a new draft correction.

Posting is one database transaction. For cash, bank, or card payments the
service creates a linked, already-posted Cash Book `payment` using the expense
amount plus tax and refreshes the existing daily summary logic. Non-cash
payment methods do not create a cash entry.

`attachment` stores metadata only (for example name, content type, size, and an
application-managed URL/storage key). The API never accepts or writes file
content, so deployments remain responsible for secure object storage,
authorization, scanning, and retention.
