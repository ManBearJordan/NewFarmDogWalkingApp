# Drop-in Fixes Implementation - COMPLETE ✅

## Summary
All the drop-in fixes specified by the user have been successfully implemented and tested.

## ✅ Fix A: Canonical Columns and Proper Range Compare

**Implemented**: Updated BookingsTab to use canonical columns with proper datetime comparison

**Changes Made**:
- Added canonical `start`, `end`, `dogs`, `service_name` columns to database schema
- Updated `refresh_table()` method to use the exact query specified:
  ```sql
  SELECT b.id,
         COALESCE(c.name,'(No client)')               AS client,
         COALESCE(b.service,b.service_name,'')        AS service,
         b.start, b.end, b.location, b.dogs,
         COALESCE(b.status,'')                        AS status,
         COALESCE(b.price_cents,0)                    AS price_cents,
         COALESCE(b.notes,'')                         AS notes
    FROM bookings b
LEFT JOIN clients c ON c.id = b.client_id
   WHERE COALESCE(b.deleted,0)=0
     AND datetime(b.start) >= datetime(?)
     AND datetime(b.start) <  datetime(?)
ORDER BY b.start ASC
  ```
- Added `_show_week_of()` method to automatically show the week containing a new booking
- Updated `add_booking()` to call `_show_week_of(start_iso)` after successful insertion

**Test Results**: ✅ PASSED
- Found 2 bookings in next week (including booking 1000)
- Query uses canonical columns and proper datetime comparison
- Bookings appear in correct week view after creation

## ✅ Fix B: Line Items Dialog Crashes (KeyError: 'display')

**Implemented**: Both defensive measures as specified

**Changes Made**:
1. **Updated `list_catalog_for_line_items()`** in `stripe_integration.py`:
   ```python
   def list_catalog_for_line_items():
       out = []
       for price in stripe.Price.list(active=True, expand=["data.product"]).auto_paging_iter():
           amount_cents = int(price.unit_amount or 0)
           nickname = getattr(price, "nickname", None)
           prod = getattr(price, "product", None)
           prod_name = getattr(prod, "name", None) if prod else None
           display = nickname or prod_name or price.id
           out.append({
               "price_id": price.id,
               "amount_cents": amount_cents,
               "price_nickname": nickname,
               "product_id": getattr(prod, "id", None) if prod else None,
               "product_name": prod_name,
               "display": display,         # <-- guaranteed now
           })
       return out
   ```

2. **Made LineItemsDialog tolerant** in `app.py`:
   ```python
   # instead of: combo.addItem(p["display"], p)
   label = p.get("display") or p.get("price_nickname") or p.get("label") or p.get("product_name", "Item")
   if not label or label == "Item":
       #
