-- Clean up existing duplicate bookings
-- This script keeps one copy of each (client_id, service_type, start, end) and deletes the rest
-- If some duplicates already have stripe_invoice_id, it keeps the one that has the invoice

-- First, update duplicates to match invoice information if needed
UPDATE bookings 
SET stripe_invoice_id = (
    SELECT stripe_invoice_id 
    FROM bookings b2 
    WHERE b2.client_id = bookings.client_id 
      AND b2.service_type = bookings.service_type 
      AND b2.start = bookings.start 
      AND b2.end = bookings.end 
      AND b2.stripe_invoice_id IS NOT NULL 
    LIMIT 1
)
WHERE stripe_invoice_id IS NULL
  AND EXISTS (
    SELECT 1 FROM bookings b3 
    WHERE b3.client_id = bookings.client_id 
      AND b3.service_type = bookings.service_type 
      AND b3.start = bookings.start 
      AND b3.end = bookings.end 
      AND b3.stripe_invoice_id IS NOT NULL
  );

-- Now delete duplicates, keeping the one with the lowest ID (or the one with an invoice if available)
DELETE FROM bookings
WHERE id NOT IN (
  SELECT MIN(CASE 
    WHEN stripe_invoice_id IS NOT NULL THEN id - 1000000  -- Prioritize rows with invoices
    ELSE id 
  END) 
  FROM bookings
  WHERE COALESCE(deleted, 0) = 0
  GROUP BY client_id, service_type, start, end
);

-- Verify the cleanup
SELECT 
  client_id, 
  service_type, 
  start, 
  end, 
  COUNT(*) as count,
  GROUP_CONCAT(id) as booking_ids,
  GROUP_CONCAT(stripe_invoice_id) as invoice_ids
FROM bookings 
WHERE COALESCE(deleted, 0) = 0
GROUP BY client_id, service_type, start, end
HAVING COUNT(*) > 1;
