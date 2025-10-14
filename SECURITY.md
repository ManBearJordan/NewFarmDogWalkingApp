# Security Policy

## Staff-Only Key Update Procedures

### Stripe API Key Management

#### Access Control
- Stripe API key updates require **staff user permissions**
- Only users with `is_staff=True` can access the Stripe configuration interface
- Key updates are logged in the Django admin for audit purposes

#### Key Update Process
1. **Admin Interface Method** (Recommended for Development):
   - Navigate to the admin URL (default: `/django-admin/`, configurable via `DJANGO_ADMIN_URL`) and log in as a staff user
   - Go to the Stripe configuration section at `/stripe/`
   - Enter the new API key in the secure form
   - Click "Update Key" to save
   - The system validates the key format before storing

2. **Environment Variable Method** (Recommended for Production):
   - Set `STRIPE_API_KEY` in the environment or `.env` file
   - Restart the application to load the new key
   - Environment variables take precedence over database-stored keys

#### Key Storage Security
- **Environment Variables**: Stored in OS environment, not persisted to disk
- **Keyring Storage**: When `USE_KEYRING=1`, keys are stored in OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- **Database Storage**: Encrypted using Django's built-in field encryption (fallback method)

#### Key Validation
- The system validates Stripe key format (`sk_test_*` or `sk_live_*`)
- Invalid keys are rejected before storage
- Test/Live mode is automatically detected and displayed in the admin interface

### Administrative Access

#### Admin URL Security
- The Django admin interface is **not** at the default `/admin/` path for security
- The admin URL is configurable via the `DJANGO_ADMIN_URL` environment variable
- Default path is `/django-admin/` (safer than the common `/admin/`)
- **Production Recommendation**: Set `DJANGO_ADMIN_URL` to a secret, random path in your `.env` file:
  ```bash
  DJANGO_ADMIN_URL=sk-hd7a4v0-admin/
  ```
  (Keep the trailing slash)
- This obscurity provides additional protection against automated admin login attacks
- Consider adding IP whitelisting or additional authentication (e.g., Cloudflare Zero Trust) for the admin path

#### Staff User Requirements
- Staff users must have strong passwords (Django's built-in password validation)
- Regular password rotation is recommended
- Two-factor authentication should be considered for production environments

#### Session Management
- Staff sessions follow Django's default timeout settings
- Sessions are invalidated on logout
- Session data is stored securely (database or cache backend)

## Session and CSRF Defaults

### Session Security
Django's default session security settings are used:

```python
# Session cookie settings (Django defaults)
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_HTTPONLY = True  # Prevent XSS access to session cookies
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

# Session expiry
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False
```

#### Production Recommendations
For production deployments, add these settings:

```python
# Enable secure cookies (HTTPS only)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Additional security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### CSRF Protection
Cross-Site Request Forgery protection is enabled by default:

```python
# CSRF middleware is included in MIDDLEWARE setting
'django.middleware.csrf.CsrfViewMiddleware'

# CSRF settings (Django defaults)
CSRF_COOKIE_AGE = 31449600  # 1 year
CSRF_COOKIE_HTTPONLY = False  # JavaScript needs access for AJAX
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False  # Uses cookies by default
```

#### CSRF Token Usage
- All forms include CSRF tokens: `{% csrf_token %}`
- AJAX requests must include CSRF token in headers
- Stripe key update forms are protected by CSRF tokens

### Database Security

#### SQLite Configuration
The application uses SQLite by default with these security considerations:
- Database file (`app.db`) should have restricted file permissions
- Regular backups should be encrypted
- Consider database encryption for sensitive production data

#### Production Database Recommendations
For production, consider:
- PostgreSQL or MySQL with encrypted connections
- Regular automated backups
- Database user with minimal required permissions
- Network-level access controls

### Stripe Integration Security

#### API Key Security
- API keys are never logged or exposed in error messages
- Keys are masked in admin interface display
- Test vs. Live mode is clearly indicated to prevent accidental live charges

#### Webhook Security
- Webhook endpoints validate Stripe signatures
- Webhook processing is idempotent to prevent duplicate processing
- Failed webhooks are logged for manual review

#### Customer Data
- Customer PII is handled according to Stripe's data handling requirements
- Client data is stored locally but linked to Stripe customer IDs
- Payment data is processed by Stripe, not stored locally

### Access Logging

#### Admin Actions
- All admin actions are logged by Django's built-in admin logging
- Stripe key updates are recorded with timestamp and user
- Failed login attempts are logged

#### Application Logging
Default Django logging configuration captures:
- Authentication attempts
- Permission denied errors  
- System errors and exceptions

### Vulnerability Reporting

If you discover a security vulnerability, please:
1. **Do not** create a public GitHub issue
2. Email the security team directly (contact information in repository)
3. Provide detailed information about the vulnerability
4. Allow reasonable time for fix before public disclosure

### Security Updates

#### Dependency Management
- Regularly update Python dependencies using `pip-audit` or similar tools
- Django security updates should be applied promptly
- Stripe library updates should be tested and applied regularly

#### Monitoring
- Monitor Django security announcements
- Subscribe to Stripe security notifications
- Review access logs regularly for suspicious activity

### Compliance Considerations

#### Data Protection
- Client personal information is handled according to applicable privacy laws
- Data retention policies should be established
- Data deletion procedures should be documented

#### PCI Compliance
- Payment processing is handled entirely by Stripe
- No credit card data is stored locally
- Application architecture follows PCI DSS guidance for e-commerce

### Security Checklist for Production

- [ ] Enable HTTPS with valid SSL certificate
- [ ] Set secure cookie flags (`SECURE=True`)
- [ ] **Set `DJANGO_ADMIN_URL` to a secret, random path** (not the default)
- [ ] Configure proper file permissions on application directories
- [ ] Enable Django security middleware settings
- [ ] Set up proper logging and monitoring
- [ ] Implement regular backup procedures
- [ ] Configure firewall rules for database access
- [ ] Set up environment variable management (no secrets in code)
- [ ] Enable staff user password requirements
- [ ] Configure session timeout appropriate for use case
- [ ] Set up Stripe webhook signature validation
- [ ] Implement proper error handling (no sensitive data in error messages)
- [ ] Configure database connection encryption
- [ ] Set up dependency vulnerability scanning
- [ ] Implement access audit procedures
- [ ] Consider additional admin path protection (IP whitelisting, Cloudflare Access, etc.)