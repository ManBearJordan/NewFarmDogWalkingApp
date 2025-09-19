# NewFarmDogWalkingApp — Clean Rewrite Skeleton

This branch provides a minimal, clearer Django skeleton and a focused Stripe integration.

Key points:
- Stripe secret is read from environment variables (STRIPE_SECRET_KEY). Optionally, a system keyring may be used as a fallback by the provided helper.
- The repo contains a minimal Django project (newfarm/) and a core app with a simplified StripeSettings model for admin use.
- No secrets or keys are committed.

Local quickstart (development):
1. Create a virtualenv and install requirements:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

2. Set STRIPE_SECRET_KEY in your environment for testing.

3. Run migrations and start the dev server (if you enable Django fully):
   python manage.py migrate
   python manage.py runserver

For now this branch provides a clear starting point; follow-up PRs will add features and tests as needed.