# NewFarmDogWalkingApp — Clean Rewrite Skeleton

This repo has been reset to a minimal, secure starting point for the desktop/web app.
Key points:
- Stripe secret is read from the STRIPE_SECRET_KEY environment variable.
- Optional secure fallback: system keyring (Windows Credential Manager on Windows).
- No secret keys are committed to the repo.

## Running locally

To set up the development environment:

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run database migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
   python manage.py runserver
   ```

Local quickstart (user-ready):
1) Install runtime and dependencies listed in requirements.txt.
2) On first app launch the GUI admin will prompt the user to paste their Stripe secret key once.
   The app stores it securely (keyring) and provides an Admin → Stripe Key action to replace it.
3) Platform administrators can set STRIPE_SECRET_KEY in the environment for automated deployments.