# Customer module

Customers are master records owned by a company. `branch_id` is optional for
company-wide customers; when present, the branch must belong to the same
company. API scope is taken from the authenticated permission context and the
validated `company_id`/`branch_id` query parameters on create/list requests,
never from mutable customer data. Branch-scoped reads include company-wide
records, while records belonging to another branch are excluded.

Customer operations do not create or modify financial transactions. Deactivate
sets `status=inactive`; DELETE is an audited soft delete.
