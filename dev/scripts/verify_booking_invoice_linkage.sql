-- Verification script to check booking-invoice linkage
-- This helps verify that the idempotent system is working correctly

-- Check bookings with their invoice status
SELECT 
    id, 
    client_id, 
    service_type, 
    start, 
    end, 
    status, 
    stripe_invoice_id,
    CASE 
        WHEN stripe_invoice_id IS NOT NULL THEN 'Has Invoice'
        ELSE 'No Invoice'
    END as invoice_status
FROM bookings
WHERE COALESCE(deleted, 0) = 0
ORDER BY start DESC, id DESC;

-- Check for any remaining duplicates
SELECT 
    client_id, 
    service_type, 
    start, 
    end, 
    COUNT(*) as duplicate_count,
    GROUP_CONCAT(id) as booking_ids,
    GROUP_CONCAT(stripe_invoice_id) as invoice_ids
FROM bookings 
WHERE COALESCE(deleted, 0) = 0
GROUP BY client_id, service_type, start, end
HAVING COUNT(*) > 1;

-- Summary statistics
SELECT 
    COUNT(*) as total_bookings,
    COUNT(stripe_invoice_id) as bookings_with_invoices,
    COUNT(*) - COUNT(stripe_invoice_id) as bookings_without_invoices,
    ROUND(COUNT(stripe_invoice_id) * 100.0 / COUNT(*), 2) as invoice_coverage_percent
FROM bookings 
WHERE COALESCE(deleted, 0) = 0;
