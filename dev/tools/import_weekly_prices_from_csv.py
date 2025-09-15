# tools/import_weekly_prices_from_csv.py
# Import weekly subscription PRICES from a CSV into Stripe.
# - Forces recurring week/1
# - Ensures product exists
# - Upserts by metadata.price_code (reuses if amount same; archives old if amount changed)
# - Flexible headers: product_name|name|product_lookup, price_nickname|nickname, aud_amount_cents|unit_amount_cents|amount_cents

from __future__ import annotations
import csv, os, sys, typing as t
import stripe

# 🔒 Your live key hard-coded so no env var is needed
stripe.api_key = "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"

def die(msg: str) -> t.NoReturn:
    print(f"ERROR: {msg}")
    sys.exit(1)

def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def norm(row: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        if k in row and str(row[k]).strip() != "":
            return str(row[k]).strip()
    return default

def find_product_by_name(name: str) -> str | None:
    if not name: return None
    try:
        res = stripe.Product.search(query=f"name:'{name}'", limit=1)
        if res and res.data: return res.data[0].id
    except Exception:
        pass
    name_l = name.lower()
    for p in stripe.Product.list(limit=100).auto_paging_iter():
        if (p.name or "").lower() == name_l:
            return p.id
    return None

def ensure_product(name: str) -> str:
    pid = find_product_by_name(name)
    if pid: return pid
    prod = stripe.Product.create(name=name, active=True, metadata={})
    return prod.id

def find_price_by_code(price_code: str) -> str | None:
    if not price_code: return None
    try:
        res = stripe.Price.search(query=f"metadata['price_code']:'{price_code}'", limit=1)
        if res and res.data: return res.data[0].id
    except Exception:
        pass
    for pr in stripe.Price.list(limit=100).auto_paging_iter():
        if (pr.metadata or {}).get("price_code") == price_code:
            return pr.id
    return None

def get_price_amount(price_id: str) -> int | None:
    pr = stripe.Price.retrieve(price_id)
    return getattr(pr, "unit_amount", None)

def archive_price(price_id: str):
    stripe.Price.modify(price_id, active=False)

def main():
    # Default to tools\stripe_prices_weekly_no_gst.csv if no arg provided
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        csv_path = sys.argv[1]
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(here, "stripe_prices_weekly_no_gst.csv")

    if not os.path.exists(csv_path):
        die(f"Prices CSV not found: {csv_path}")

    rows = read_csv(csv_path)
    created = reused = replaced = 0

    for r in rows:
        product_name = norm(r, "product_name", "name", "product_lookup")
        if not product_name:
            die("Row missing product_name/name/product_lookup.")

        price_code = norm(r, "price_code")
        if not price_code:
            die("Row missing price_code.")

        nickname = norm(r, "price_nickname", "nickname") or f"{product_name} (Weekly)"

        # amount (cents) from any of these headers
        amount = None
        for k in ("aud_amount_cents","unit_amount_cents","amount_cents"):
            if r.get(k):
                try:
                    amount = int(float(str(r[k]).strip()))
                    break
                except Exception:
                    pass
        if not amount or amount <= 0:
            die(f"Invalid amount for price_code={price_code}. Provide aud_amount_cents (in cents).")

        currency = (norm(r, "currency") or "aud").lower()

        # Build metadata (pass through explicit fields + any metadata.*)
        md = {
            "price_code": price_code,
            "service_code": norm(r, "service_code", "metadata.service_code"),
            "visits_per_week": norm(r, "visits_per_week"),
            "billing": norm(r, "billing", "metadata.billing") or "subscription",
            "plan": norm(r, "plan", "metadata.plan") or "weekly",
        }
        for k, v in r.items():
            if k.startswith("metadata.") and str(v).strip():
                md[k.split("metadata.",1)[1]] = str(v).strip()

        product_id = ensure_product(product_name)

        existing_id = find_price_by_code(price_code)
        if existing_id:
            old_amt = get_price_amount(existing_id)
            if old_amt == amount:
                stripe.Price.modify(existing_id, nickname=nickname or None, metadata=md)
                print(f"REUSE: {product_name} -> {nickname} ({price_code}) = ${amount/100:.2f} -> {existing_id}")
                reused += 1
                continue
            else:
                archive_price(existing_id)
                print(f"REPLACE: archived {existing_id} (old amount {old_amt}), creating new for {price_code}")
                replaced += 1

        pr = stripe.Price.create(
            product=product_id,
            unit_amount=amount,
            currency=currency,
            nickname=nickname or None,
            recurring={"interval": "week", "interval_count": 1},
            metadata=md,
        )
        print(f"CREATE: {product_name} -> {nickname} ({price_code}) = ${amount/100:.2f} -> {pr.id}")
        created += 1

    print(f"\nDone. Created: {created}, Replaced: {replaced}, Reused: {reused}")

if __name__ == "__main__":
    main()
