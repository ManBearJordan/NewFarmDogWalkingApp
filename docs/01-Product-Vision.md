# 01 — Product Vision

**Goal:** Run a modern, server-backed booking & CRM system for New Farm Dog Walking with:
- Internal **ops console** (web app) replacing the older desktop-only flow.
- **Anywhere access** via browser or mobile app wrapper.
- **Customer-facing** booking on the public website that flows into Stripe and the back-office calendar.
- Robust **Stripe** integration (customers, invoices, subscriptions, payment links).
- **Calendar** and **subscriptions** with automatic materialization to holds and bookings.
- Strong emphasis on reliability, correctness, and auditability.

## Personas
- **Owner/Operator (Jordan):** manages clients, pets, routes, invoices, credits, and subscriptions.
- **Customer:** books walks/daycare/overnight services, views invoices, updates payment info, cancels/reschedules within policy.
- **Staff/Contractor (optional future):** sees assigned jobs, marks complete, uploads notes/photos.

## Non-Goals (initial)
- Marketplace features (multi-business).
- Complex route optimization (basic is fine at first).
- Native-only mobile—use PWA or a thin wrapper.
