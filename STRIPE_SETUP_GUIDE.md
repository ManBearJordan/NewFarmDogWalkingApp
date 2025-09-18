# Stripe API Key Setup Guide

## Security Notice
This application now uses environment variables for Stripe API keys instead of hard-coded secrets. This is a security best practice.

## Setup Instructions

### 1. Set Environment Variable
You need to set your Stripe secret key as an environment variable before running the application.

#### Windows (Command Prompt):
```cmd
set STRIPE_SECRET_KEY=sk_live_your_actual_key_here
```

#### Windows (PowerShell):
```powershell
$env:STRIPE_SECRET_KEY="sk_live_your_actual_key_here"
```

#### Linux/Mac:
```bash
export STRIPE_SECRET_KEY=sk_live_your_actual_key_here
```

### 2. Alternative Environment Variable Names
The application will check for these environment variables in order:
1. `STRIPE_SECRET_KEY`
2. `STRIPE_API_KEY`

### 3. For Development
For development, you can use test keys:
```cmd
set STRIPE_SECRET_KEY=sk_test_your_test_key_here
```

### 4. Permanent Setup (Windows)
To set the environment variable permanently on Windows:
1. Open System Properties → Advanced → Environment Variables
2. Add a new User or System variable:
   - Name: `STRIPE_SECRET_KEY`
   - Value: `sk_live_your_actual_key_here`

## Security Best Practices
- ✅ Never commit API keys to version control
- ✅ Use environment variables for secrets
- ✅ Use test keys for development
- ✅ Rotate keys regularly
- ✅ Restrict key permissions in Stripe Dashboard

## Verification
To verify your setup is working, the application will show an error if no API key is found when making Stripe API calls.
