# 13 — Security & Privacy

- Store money as cents; never log full card data (Stripe handles PCI).
- Encrypt stored Stripe key; minimize exposure in logs.
- CSRF enabled; session cookies secure; HTTPS required.
- Role-based access: staff vs customer portal.
- Audit logs for critical actions (invoice creation/finalization mapping, credit adjustments).
