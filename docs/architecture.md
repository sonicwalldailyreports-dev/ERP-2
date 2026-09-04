# Architecture

## Principles

The application is a modular monolith. One deployable backend owns all modules and one frontend consumes its versioned API. Modules are separated by responsibility, not by process. Tenant context (`company_id` and optional `branch_id`) is derived from authenticated server-side context; it is never hard-coded or trusted from frontend controls.

## Backend boundaries

`app/api` contains transport concerns and dependency wiring. `app/modules/*/router.py` exposes endpoints, `service.py` owns business workflows, `repository.py` owns persistence queries, `schemas.py` defines API contracts, and `models.py` defines SQLAlchemy persistence models. Services do not depend on FastAPI request objects and routes never contain business logic.

`app/core` contains settings, security primitives, and cross-cutting errors. `app/db` contains the async engine, session factory, and declarative base. `app/repositories` and `app/services` contain only genuinely shared infrastructure; module-specific behavior stays within its module.

## Frontend boundaries

`src/app` configures the application and providers. `src/features` owns module UI and queries. `src/services` owns HTTP transport, `src/types` owns API types, `src/stores` is reserved for durable client-only state, and `src/components` contains reusable presentation components. Server state belongs in TanStack Query; Zustand is not introduced until a real cross-feature client-state requirement exists.

## Data and transaction rules

Alembic is the only mechanism for production schema changes. Financial workflows must use one database transaction and explicit posting/approval states. API responses use Pydantic schemas, never SQLAlchemy model instances directly. Important mutations will emit audit events.

## Planned module layout

Backend modules: auth, users, roles, companies, branches, customers, vendors, accounts, cashbook, expenses, transactions, reports, audit, and notifications. Frontend features mirror those business boundaries plus dashboard and administration.

