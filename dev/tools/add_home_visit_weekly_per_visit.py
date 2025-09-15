# tools/add_home_visit_weekly_per_visit.py
# Adds/updates a WEEKLY (per-visit) recurring Stripe Price on your existing
# Home Visit 30m products:
#   - "Home Visit – 30m (1×/day)"
#   - "Home Visit – 30m (2×/day)"
# The weekly price's unit_amount == the one-time per-visit amount.
# You control visits/week by setting the subscription item's QUANTITY.
# No visits_per_week metadata is written.

import stripe

# 🔒 Your live key embedded exactly as requested
stripe.api_key = "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"

CURRENCY = "aud"
NICKNAME = "Weekly (per visit)"  # how it shows in Stripe
TARGET_META = {
    "service_code": "HOME_30",
    "default_duration_min": "30",
    "capacity_type": "visit",
    "cadence": "weekly",
    "unit": "visit",
}

# Exact names you showed
PRODUCT_NAMES = [
    "Home Visit – 30m (1×/day)",
    "Home Visit – 30m (2×/day)",
]

def find_product_by_name_exact(name: str):
    # Try search API first
    try:
        res = stripe.Product.search(query=f"name:'{name}'", limit=1)
        if res and res.data:
            return res.data[0]
    except Exception:
        pass
    # Fallback: scan
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if (getattr(p, "name", "") or "").strip() == name:
            return p
    return None

def most_recent_one_time_aud_amount(product_id: str):
    latest = -1
    chosen = None
    for pr in stripe.Price.list(product=product_id, active=True, limit=100).auto_paging_iter():
        if getattr(pr, "recurring", None):
            continue
        if (pr.currency or "").lower() != CURRENCY:
            continue
        created = getattr(pr, "created", 0) or 0
        if pr.unit_amount and created >= latest:
            latest = created
            chosen = pr.unit_amount
    return chosen

def find_existing_weekly_per_visit_price(product_id: str):
    # Find a weekly recurring price on THIS product with unit=visit + cadence=weekly
    for pr in stripe.Price.list(product=product_id, active=True, limit=100).auto_paging_iter():
        rec = getattr(pr, "recurring", None)
        if not rec or rec.get("interval") != "week":
            continue
        md = getattr(pr, "metadata", {}) or {}
        if (md.get("unit") == "visit") and (md.get("cadence") == "weekly"):
            return pr
    return None

def ensure_product_metadata(prod):
    md = dict(getattr(prod, "metadata", {}) or {})
    changed = False
    for k, v in {"service_code": "HOME_30", "default_duration_min": "30", "capacity_type": "visit"}.items():
        if str(md.get(k, "")).strip() != str(v):
            md[k] = v
            changed = True
    if changed:
        stripe.Product.modify(prod.id, metadata=md, active=True)

def upsert_weekly_per_visit_price(prod):
    ensure_product_metadata(prod)
    amount = most_recent_one_time_aud_amount(prod.id)
    if not isinstance(amount, int) or amount <= 0:
        print(f"SKIP: {prod.name} — no active one-time AUD price found.")
        return

    existing = find_existing_weekly_per_visit_price(prod.id)
    if existing:
        if (existing.unit_amount or 0) == amount and (existing.currency or "").lower() == CURRENCY:
            # Refresh name/metadata only
            md = dict(getattr(existing, "metadata", {}) or {})
            md.update(TARGET_META)
            stripe.Price.modify(existing.id, nickname=NICKNAME, metadata=md)
            print(f"REUSE: {prod.name} -> {NICKNAME} = ${amount/100:.2f} -> {existing.id}")
            return
        else:
            # Prices are immutable; archive and create new with correct amount
            stripe.Price.modify(existing.id, active=False)
            print(f"ARCHIVE: {existing.id} (old amount {existing.unit_amount})")

    pr = stripe.Price.create(
        product=prod.id,
        unit_amount=amount,          # per-visit amount
        currency=CURRENCY,
        nickname=NICKNAME,
        recurring={"interval": "week", "interval_count": 1},
        metadata=TARGET_META,
    )
    print(f"CREATE: {prod.name} -> {NICKNAME} = ${amount/100:.2f} -> {pr.id}")

def main():
    for name in PRODUCT_NAMES:
        p = find_product_by_name_exact(name)
        if not p:
            print(f"NOT FOUND: {name}")
            continue
        upsert_weekly_per_visit_price(p)
    print("\nDone. Weekly (per-visit) prices are ready for subscriptions. Set QUANTITY = visits/week in Stripe.")

if __name__ == "__main__":
    main()
