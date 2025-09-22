# CODING_STANDARDS.md

## 1. Python/Django basics
- Python 3.11+ preferred.
- Keep functions ≤ 50 lines; split helpers when longer.
- Type hints on public functions.
- Django settings via env; no secrets in repo.

## 2. Project structure
- Business logic in `core/` (services, mappers, rules).
- HTTP views thin; call services.
- External I/O (Stripe, filesystem, calendar) in `core/adapters/` or clearly named modules.
- DB models in `core/models.py` (split into modules if it grows).

## 3. Stripe integration
- All calls go through a single helper (`core/stripe_integration.py`).
- Use idempotency keys for writes; store external IDs in our tables.
- Never assume completeness; every sync is safe to re-run.

## 4. Booking allocation rules
- Represent match/allocation as JSON in `Rule` records:
  - `matcher_json` examples: match by `price_id`, `product_id`, `metadata`, or description regex.
  - `allocation_json` examples: number of bookings, cadence, duration, date window.
- Rule engine is pure and unit-tested; no DB writes inside the allocator.

## 5. Deduplication
- Create `DedupEvent(external_id, kind)` row **before** processing; if it exists, skip.
- Compute a content hash to detect changes and allow “update without duplicate.”

## 6. Calendar output
- Provide an `ics/` endpoint and a per-client `.ics` export.
- Use UTC internally; convert to local time only for display.

## 7. Logging & errors
- Log once at boundary (webhook handler or command).
- Do not swallow exceptions; return structured error with context (ids, counts).
- Include Stripe request IDs in logs when available.

## 8. Tests
- Every service/mapping function has at least one happy-path unit test.
- One integration test per pipeline: “invoice/subscription → N bookings”.
- Add regression tests for every bug fix.

## 9. Commits / PRs
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`.
- PR description must include: what/why, risks, how tested.

## 10. Desktop wrapper
- PyWebview opens only after the local server is reachable.
- Window title shows environment (`DEV`, `PROD`).
- Quit the server gracefully when the window closes.
