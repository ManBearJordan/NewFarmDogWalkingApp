-- One-time cleanup: Deactivate future holds from cancelled subscriptions
-- Run this once to clean up any stray future holds from cancelled subs

UPDATE sub_occurrences
   SET active = 0
 WHERE active = 1
   AND stripe_subscription_id IN (
       SELECT stripe_subscription_id FROM subs 
       WHERE status NOT IN ('active','trialing')
   )
   AND date(start_dt) >= date('now');

-- Show how many records were affected
SELECT changes() as 'Records updated';
