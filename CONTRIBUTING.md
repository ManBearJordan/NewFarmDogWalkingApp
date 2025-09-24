# Contributing to New Farm Dog Walking App

Thank you for your interest in contributing to the New Farm Dog Walking App! This document provides guidelines and information for contributors.

## Branch Naming Conventions

We use a structured branch naming system to keep the repository organized and make it easy to understand the purpose of each branch.

### Branch Naming Format
```
<type>/<short-description>
```

### Branch Types

#### Feature Branches
- **Prefix**: `feature/`
- **Purpose**: New features or enhancements
- **Examples**:
  - `feature/client-portal`
  - `feature/stripe-webhooks`
  - `feature/booking-notifications`

#### Bug Fix Branches
- **Prefix**: `fix/` or `bugfix/`
- **Purpose**: Fixing bugs or issues
- **Examples**:
  - `fix/stripe-key-validation`
  - `bugfix/booking-time-conflict`
  - `fix/portal-authentication`

#### Documentation Branches
- **Prefix**: `docs/`
- **Purpose**: Documentation updates and improvements
- **Examples**:
  - `docs/api-documentation`
  - `docs/deployment-guide`
  - `docs/contributing-guidelines`

#### Chore Branches
- **Prefix**: `chore/`
- **Purpose**: Maintenance tasks, dependency updates, configuration changes
- **Examples**:
  - `chore/update-dependencies`
  - `chore/env-and-docs`
  - `chore/ci-improvements`

#### Hotfix Branches
- **Prefix**: `hotfix/`
- **Purpose**: Critical fixes that need immediate attention
- **Examples**:
  - `hotfix/security-patch`
  - `hotfix/payment-processing`

### Branch Naming Best Practices
- Use lowercase letters and hyphens (kebab-case)
- Keep descriptions short but descriptive
- Avoid special characters except hyphens
- Use present tense for action-oriented names
- Include issue numbers when applicable: `feature/client-portal-issue-123`

## Development Workflow

### 1. Setting Up Development Environment
```bash
# Clone the repository
git clone https://github.com/ManBearJordan/NewFarmDogWalkingApp.git
cd NewFarmDogWalkingApp

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 2. Creating a New Branch
```bash
# Make sure you're on main and up to date
git checkout main
git pull origin main

# Create and switch to new branch
git checkout -b feature/your-feature-name
```

### 3. Making Changes
- Make your changes in small, logical commits
- Write clear, descriptive commit messages
- Test your changes thoroughly
- Update documentation if needed

### 4. Commit Guidelines
Write clear commit messages following this format:
```
<type>: <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat: add client portal authentication

fix: resolve booking time conflict validation

docs: update API documentation for new endpoints

test: add unit tests for Stripe integration
```

## Test Commands and Procedures

### Running Tests

#### Django Test Suite
```bash
# Run all tests
python manage.py test

# Run tests with verbose output
python manage.py test --verbosity=2

# Run specific app tests
python manage.py test core

# Run specific test class
python manage.py test core.tests.test_admin_views

# Run specific test method
python manage.py test core.tests.test_admin_views.TestAdminViews.test_stripe_key_update
```

#### Alternative Test Runners
If pytest is configured:
```bash
# Run with pytest (if configured)
pytest

# Run with coverage
pytest --cov=core --cov-report=term-missing

# Run specific test file
pytest core/tests/test_admin_views.py

# Run with verbose output
pytest -v
```

### Test Organization

#### Test Structure
```
core/
├── tests/
│   ├── __init__.py
│   ├── test_admin_views.py    # Admin interface tests
│   ├── test_portal_access.py  # Client portal tests
│   ├── test_stripe_integration.py  # Stripe API tests
│   └── test_booking_logic.py  # Booking creation tests
└── test_files/
    └── test_booking_list.py   # Additional test files
```

#### Test Categories

**Unit Tests**: Test individual functions and methods
```bash
python manage.py test core.tests.test_stripe_integration
```

**Integration Tests**: Test component interactions
```bash
python manage.py test core.tests.test_booking_logic
```

**View Tests**: Test Django views and forms
```bash
python manage.py test core.tests.test_admin_views
python manage.py test core.tests.test_portal_access
```

### Writing New Tests

#### Test File Naming
- Start test files with `test_`
- Use descriptive names: `test_stripe_integration.py`
- Group related tests in the same file

#### Test Class Structure
```python
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Client

class TestClientPortal(TestCase):
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.client = Client.objects.create(
            name='Test Client',
            email='test@example.com',
            user=self.user
        )
    
    def test_portal_requires_login(self):
        """Test that portal requires authentication"""
        response = self.client.get('/portal/')
        self.assertEqual(response.status_code, 302)
    
    def test_portal_displays_client_info(self):
        """Test portal shows client information"""
        self.client.login(username='testuser', password='testpass')
        response = self.client.get('/portal/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Client')
```

#### Test Markers
Use pytest markers for test categorization:
```python
@pytest.mark.django_db
def test_database_operation():
    """Test that requires database access"""
    pass

@pytest.mark.webhook
def test_stripe_webhook():
    """Test that requires webhook functionality"""
    pass
```

### Testing Best Practices

1. **Test Independence**: Each test should be independent and not rely on other tests
2. **Clear Assertions**: Use descriptive assertion messages
3. **Test Data**: Use factories or fixtures for consistent test data
4. **Mock External Services**: Mock Stripe API calls and external dependencies
5. **Edge Cases**: Test boundary conditions and error scenarios

### Pre-commit Testing
Before committing changes:
```bash
# Run all tests
python manage.py test

# Check for linting issues (if configured)
flake8 .

# Run specific tests related to your changes
python manage.py test core.tests.test_admin_views
```

### Continuous Integration
The project uses GitHub Actions for CI. Tests run automatically on:
- Pull requests
- Pushes to main branch
- Manual workflow dispatch

Check `.github/workflows/` for CI configuration.

## Code Style Guidelines

### Python Code Style
- Follow PEP 8 guidelines
- Use 4 spaces for indentation
- Maximum line length: 88 characters (Black formatter default)
- Use meaningful variable and function names

### Django Conventions
- Follow Django's coding style guidelines
- Use Django's built-in features when possible
- Keep views focused and minimal
- Use Django's forms for data validation

### Documentation
- Write docstrings for all functions and classes
- Update README.md for significant changes
- Add comments for complex business logic
- Update API documentation when adding endpoints

## Pull Request Process

### 1. Before Creating PR
- Ensure all tests pass
- Update documentation if needed
- Rebase your branch on latest main
- Write clear commit messages

### 2. Creating the PR
- Use a descriptive title
- Provide detailed description of changes
- Reference related issues: "Fixes #123"
- Add screenshots for UI changes
- Request appropriate reviewers

### 3. PR Review Process
- Address all review comments
- Keep discussions constructive
- Make requested changes in new commits
- Update tests if functionality changes

### 4. Merging
- PRs require approval from maintainer
- All CI checks must pass
- Squash commits when merging (if requested)

## Getting Help

### Resources
- **Documentation**: Check the `docs/` folder
- **Issues**: Browse existing GitHub issues
- **Discussions**: Use GitHub Discussions for questions

### Contact
- Create an issue for bugs or feature requests
- Use discussions for general questions
- Contact maintainers directly for security issues

## Development Tips

### Local Development
- Use the development server: `python manage.py runserver`
- Enable debug mode in `.env`: `DEBUG=1`
- Use the admin interface for testing: `/admin/`

### Database Management
- Reset database: `rm app.db && python manage.py migrate`
- Create test data: Use Django admin or management commands
- Backup data: `python manage.py dumpdata > backup.json`

### Stripe Testing
- Use Stripe test keys (start with `sk_test_`)
- Use Stripe test cards for payment testing
- Monitor Stripe dashboard for webhook events

Thank you for contributing to the New Farm Dog Walking App!