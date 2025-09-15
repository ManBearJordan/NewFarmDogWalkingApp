import csv, os
import stripe

# Reads single prices by metadata.price_code and writes weekly product/price CSVs
# Requires: STRIPE_API_KEY in env (your live key)

PRICE_MAP = [
    # (single_code, weekly_code, product_name, service_code, capacity_type, default_duration_min, price_nickname)
    ("WALK_SHORT_SINGLE", "WALK_SHORT_WEEKLY", "Short Walk", "WALK_SHORT", "walk", 30, "Short Walk (Weekly)"),
    ("WALK_LONG_SINGLE",  "WALK_LONG_WEEKLY",  "Long Walk",  "WALK_LONG",  "walk", 60, "Long Walk (Weekly)"),
    ("HOME_30_SINGLE",    "HOME_30_WEEKLY",    "Home Visit – 30m", "HOME_30", "visit", 30, "Home Visit – 30m (Weekly)"),
    ("DAYCARE_SINGLE",    "DAYCARE_WEEKLY",    "Doggy Daycare (per day)", "DAYCARE_DAY", "daycare", 480, "Daycare (Weekly)"),
]

STRIPE_KEY = os.getenv("STRIPE_API_KEY")
if not STRIPE_KEY:
    raise SystemExit("Set STRIPE_API_KEY first (your live secret key).")

stripe.api_key = STRIPE_KEY

def find_single_amount_cents(single_code: str) -> int | None:
    # Find a price with metadata.price_code == single_code
    prices = stripe.Price.list(limit=100, expand=["data.product"])
    for p in prices.auto_paging_iter():
        md = getattr(p, "metadata", {}) or {}
        if md.get("price_code") == single_code and p.get("active", True):
            amt = p.get("unit_amount")
            if isinstance(amt, int):
                return amt
    return None

def main():
    products_csv = "stripe_products_weekly_no_gst.csv"
    prices_csv   = "stripe_prices_weekly_no_gst.csv"

    prod_rows = []
    price_rows = []

    for single_code, weekly_code, product_name, service_code, capacity_type, default_duration_min, nickname in PRICE_MAP:
        amount = find_single_amount_cents(single_code)
        if amount is None:
            print(f"[SKIP] Couldn’t find single price with price_code={single_code}")
            continue

        # Product metadata row
        prod_rows.append({
            "name": product_name,
            "description": f"{product_name} — weekly subscription (1x/week, use quantity for more)",
            "service_code": service_code,
            "capacity_type": capacity_type,
            "default_duration_min": default_duration_min,
        })

        # Price metadata row (weekly)
        price_rows.append({
            "product_name": product_name,
            "nickname": nickname,
            "aud_amount_cents": amount,
            "interval": "week",
            "interval_count": 1,
            "visits_per_week": 1,
            "pack_qty": 1,
            "price_code": weekly_code,
        })

        print(f"[OK] {product_name}: single={single_code} ${amount/100:.2f} -> weekly={weekly_code}")

    # Write products CSV
    with open(products_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name","description","service_code","capacity_type","default_duration_min"])
        w.writeheader()
        for r in prod_rows:
            w.writerow(r)

    # Write prices CSV
    with open(prices_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "product_name","nickname","aud_amount_cents","interval","interval_count","visits_per_week","pack_qty","price_code"
        ])
        w.writeheader()
        for r in price_rows:
            w.writerow(r)

    print(f"\nWrote:\n - {products_csv}\n - {prices_csv}\nReady to import with tools/import_from_csv.py")

if __name__ == "__main__":
    main()
