New Farm Dog Walking — Desktop App (v0.4)
- Adds REAL Stripe **Invoices** support + Invoices tab.
- SECURE Stripe secret key storage using Windows Credential Manager.
- Keep using Start-App.bat. No council logic.

** SECURITY UPDATE - STRIPE KEY MANAGEMENT **
The app now stores your Stripe secret key securely in your system's credential manager:
- Windows: Windows Credential Manager
- macOS: Keychain (future support)  
- Linux: Secret Service (future support)

Keys are NEVER stored in plaintext files or committed to version control.

** SETUP - IMPORTANT **
On first run, the app will show a GUI dialog to collect your Stripe secret key:

1) Run the application normally with Start-App.bat
2) A friendly dialog box will appear with setup instructions
3) Enter your Stripe secret key (sk_test_... or sk_live_...) in the secure input field
4) The key will be stored securely in Windows Credential Manager
5) On subsequent runs, the key will be retrieved automatically

**GUI Features:**
✅ User-friendly dialog with clear instructions
✅ Password-style input field that hides your key
✅ Automatic fallback to console on headless systems

Alternative setup methods:
- Command line: python stripe_key_manager.py set
- Environment variable: set STRIPE_SECRET_KEY=your_key_here

👉 **See README.md for detailed GUI setup documentation**

** SECURITY BENEFITS **
✅ Keys stored in secure system credential manager
✅ No plaintext key files that can be accidentally committed
✅ Automatic key retrieval on app startup
✅ Cross-platform design for future server/mobile integration
✅ Environment variable fallback for development

** LEGACY SETUP (NOT RECOMMENDED) **
The old method still works but is less secure:
1) Copy secrets_config.example.py to secrets_config.py
2) Edit secrets_config.py and replace the fake key with your actual Stripe secret key
3) NEVER commit secrets_config.py to version control (it's already in .gitignore)

Example:
  STRIPE_SECRET_KEY = "sk_live_YOUR_ACTUAL_KEY_HERE"

How to invoice:
1) Add a Client (with email).
2) Create a Booking.
3) Select the booking and click **Create Stripe Invoice**.
   - The app creates a one-off invoice in Stripe, finalizes it, and opens the hosted invoice page.
   - Stripe emails the invoice to the client (if your account has emailing enabled) or you can copy the link.
4) Open the **Invoices** tab → **Refresh from Stripe** to see status updates. Double-click to open the hosted link.
