New Farm Dog Walking — Desktop App (v0.3)
- Adds REAL Stripe **Invoices** support + Invoices tab.
- Keep using Start-App.bat. No council logic.

How to invoice:
1) Add a Client (with email).
2) Create a Booking.
3) Select the booking and click **Create Stripe Invoice**.
   - The app creates a one-off invoice in Stripe, finalizes it, and opens the hosted invoice page.
   - Stripe emails the invoice to the client (if your account has emailing enabled) or you can copy the link.
4) Open the **Invoices** tab → **Refresh from Stripe** to see status updates. Double-click to open the hosted link.
