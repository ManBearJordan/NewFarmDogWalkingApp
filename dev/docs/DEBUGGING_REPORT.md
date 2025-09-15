# Dog Walking App Debugging Report

## Executive Summary

I've conducted a comprehensive analysis of your dog walking application codebase and identified several key issues related to `service_type`, `service_code`, `price_code`, and customer ID handling in subscription-based bookings. Here's what I found:

## Issues Identified

### 1. Service Type Derivation Issues ❌

**Problem**: The `service_type_from_label()` function in `stripe_invoice_bookings.py` has incomplete logic for handling complex service names with special characters.

**Evidence**: Test results show:
- `'Home Visit – 30m (1×/day)'` → `'HOME_VISIT_–_30M_(1×/DAY)'` (should be `'HOME_VISIT_30M_SINGLE'`)
- `'Poop Scoop – One-time'` → `'POOP_SCOOP_–_ONE-TIME'` (should be `'SCOOP_SINGLE'`)

**Location**: `stripe_invoice_bookings.py:15-25`

**Impact**: This causes inconsistent service type codes in the database, making it difficult to properly categorize and report on services.

### 2. Customer ID Resolution in Subscription Bookings ⚠️

**Problem**: Multiple inconsistent approaches to resolving customer IDs from Stripe data to local client records.

**Evidence Found**:
- In `app.py` (SubscriptionsTab): Uses both `stripe_customer_id` and `stripeCustomerId` columns
- In `stripe_invoice_bookings.py`: Complex fallback logic that can create duplicate clients
- Database schema has both `stripe_customer_id` and `stripeCustomerId` columns for compatibility

**Locations**:
- `app.py:1847-1890` (subscription booking generation)
- `stripe_invoice_bookings.py:120-180` (invoice import)
- `db.py:280-285` (schema with dual columns)

**Impact**: Can lead to:
- Duplicate client records
- Bookings assigned to wrong clients
- Failed booking creation when customer resolution fails

### 3. Service Field Population Inconsistencies ⚠️

**Problem**: Multiple overlapping fields for service information with inconsistent population:

**Database Fields**:
- `service` (display label)
- `service_type` (code)
- `service_name` (alias/backup)
- `stripe_price_id` (Stripe reference)

**Evidence**: 
- `db.py:200-220` shows migration logic copying between these fields
- `app.py:1200-1250` shows complex service extraction logic with multiple fallbacks
- Different parts of the code prioritize different fields

**Impact**: 
- Inconsistent service display across the application
- Difficulty in reporting and filtering
- Potential data loss during migrations

### 4. Price Code Handling Issues ⚠️

**Problem**: `price_code` is used in CSV import tools but not consistently linked to booking records.

**Evidence**:
- `tools/import_weekly_prices_from_csv.py` uses `price_code` metadata
- `tools/import_from_csv.py` has `find_price_by_code()` function
- Main booking creation doesn't store or use `price_code` consistently

**Impact**: 
- Difficulty linking bookings back to specific price configurations
- Inconsistent pricing when services are updated

## Code Quality Issues Found

### 5. Redundant Service Type Derivation Functions

**Problem**: Multiple similar functions across different files:

**Locations**:
- `stripe_invoice_bookings.py:15` - `service_type_from_label()`
- `app.py:1300` - `_derive_service_type_from_label()`
- `fix_booking_issues.py:200` - `derive_service_type_from_label()`

**Impact**: Code duplication and inconsistent behavior

### 6. Complex Fallback Logic

**Problem**: Overly complex fallback chains for service and customer resolution make debugging difficult.

**Example** from `stripe_invoice_bookings.py:80-120`:
```python
# Try metadata first, then line items, then price metadata, then product metadata
# Each with multiple field name variations
```

## Positive Findings ✅

### What's Working Well:

1. **Database Cleanup**: Recent cleanup scripts have successfully removed most "Subscription" placeholder records
2. **Booking Validation**: Current bookings all have proper `client_id`, `service_type`, and service labels
3. **Credit System**: Client credit handling is working correctly
4. **Duplicate Prevention**: Unique constraints prevent duplicate bookings

## Recommendations

### High Priority Fixes:

1. **Standardize Service Type Derivation**:
   - Create a single, comprehensive `service_type_from_label()` function
   - Handle special characters properly (–, ×, parentheses)
   - Use it consistently across all import/creation functions

2. **Simplify Customer Resolution**:
   - Standardize on `stripe_customer_id` column (deprecate `stripeCustomerId`)
   - Create a single `resolve_customer_id()` function
   - Add proper error handling for unresolvable customers

3. **Consolidate Service Fields**:
   - Use `service` for display labels
   - Use `service_type` for codes
   - Deprecate `service_name` (redundant with `service`)
   - Always populate `stripe_price_id` when available

### Medium Priority Improvements:

4. **Add Price Code Tracking**:
   - Store `price_code` in booking records
   - Link bookings to price configurations for better reporting

5. **Improve Error Handling**:
   - Add validation for required fields before booking creation
   - Better error messages for customer resolution failures

### Low Priority Cleanup:

6. **Remove Code Duplication**:
   - Consolidate service type derivation functions
   - Simplify complex fallback logic

## Testing Status

- ✅ Booking Creation: Working correctly
- ✅ Database Cleanup: No orphaned records found
- ❌ Service Type Derivation: Needs improvement for special characters
- ✅ Booking Validation: All current bookings are valid

## Files Requiring Changes

### Critical:
- `stripe_invoice_bookings.py` - Fix service type derivation
- `app.py` - Standardize customer resolution in subscription bookings

### Important:
- `db.py` - Consider schema cleanup for redundant columns
- `stripe_integration.py` - Ensure consistent service field population

### Nice to Have:
- Various cleanup and test files - Remove code duplication

## Conclusion

The application is fundamentally working well, with most critical issues already resolved by previous cleanup efforts. The remaining issues are primarily around edge cases in service type derivation and some inconsistencies in data handling that could be improved for better maintainability and reliability.

The customer ID resolution for subscription bookings is working but could be simplified and made more robust. The service field population is functional but has some redundancy that could be cleaned up.

Overall, this is a well-maintained codebase with good error handling and validation in place.
