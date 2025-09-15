# tools/import_from_csv.py
# Upserts Products and Prices from CSVs (no GST). Flexible headers supported.
# Reads Stripe key from secrets_config.get_stripe_key().

from __future__ import annotations
import csv, os, sys, typing as t
import stripe
from secrets_config import get_stripe_key

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

def to_int_or_none(v: t.Any) -> t.Optional[int]:
    if v is None: return None
    s = str(v).strip()
    if s == "": return None
    try:
        return int(float(s))
    except Exception:
        return None

def clean_meta(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if v is None: 
            continue
        s = str(v).strip()
        if not s:
            continue
        if k.startswith("metadata."):
            out[k.split("metadata.",1)[1]] = s
        else:
            out[k] = s
    return out

def find_product_by_service_code(service_code: str) -> t.Optional[str]:
    if not service_code:
        return None
    try:
        res = stripe.Product.search(query=f"metadata['service_code']:'{service_code}'", limit=1)
        if res and res.data:
            return res.data[0].id
    except Exception:
        pass
    for p in stripe.Product.list(limit=100).auto_paging_iter():
        if (p.metadata or {}).get("service_code") == service_code:
            return p.id
    return None

def find_product_by_name(name: str) -> t.Optional[str]:
    if not name:
        return None
    try:
        res = stripe.Product.search(query=f"name:'{name}'", limit=1)
        if res and res.data:
            return res.data[0].id
    except Exception:
        pass
    name_l = name.lower()
    for p in stripe.Product.list(limit=100).auto_paging_iter():
        if (p.name or "").lower() == name_l:
            return p.id
    return None

def upsert_product(row: dict) -> str:
    name = norm(row, "product_name", "name")
    if not name:
        die("Product row missing 'product_name' or 'name'.")

    description = norm(row, "description")
    service_code = norm(row, "service_code")
    metadata = clean_meta({
        "service_code": service_code,
        "capacity_type": norm(row, "capacity_type"),
        "default_duration_min": norm(row, "default_duration_min"),
        "default_duration_hours": norm(row, "default_duration_hours"),
        "visits_per_day": norm(row, "visits_per_day"),
        "dogs_default": norm(row, "dogs_default"),
    })

    existing_id = find_product_by_service_code(service_code) if service_code else None
    if not existing_id:
        existing_id = find_product_by_name(name)

    if existing_id:
        stripe.Product.modify(existing_id, name=name, description=description or None, active=True, metadata=metadata)
        return existing_id
    else:
        prod = stripe.Product.create(name=name, description=description or None, active=True, metadata=metadata)
        return prod.id

def find_price_by_code(price_code: str) -> t.Optional[str]:
    if not price_code:
        return None
    try:
        res = stripe.Price.search(query=f"metadata['price_code']:'{price_code}'", limit=1)
        if res and res.data:
            return res.data[0].id
    except Exception:
        pass
    for pr in stripe.Price.list(limit=100).auto_paging_iter():
        if (pr.metadata or {}).get("price_code") == price_code:
            return pr.id
    return None

def get_price_amount(price_id: str) -> t.Optional[int]:
    pr = stripe.Price.retrieve(price_id)
    return getattr(pr, "unit_amount", None)

def archive_price(price_id: str):
    stripe.Price.modify(price_id, active=False)

def upsert_price(row: dict, product_id: str) -> str:
    nickname = norm(row, "price_nickname", "nickname")
    price_code = norm(row, "price_code")
    if not price_code:
        die("Price row missing 'price_code'.")

    amount = (
        to_int_or_none(row.get("aud_amount_cents"))
        or to_int_or_none(row.get("unit_amount_cents"))
        or to_int_or_none(row.get("amount_cents"))
        or 0
    )
    if amount <= 0:
        die(f"Invalid amount for price_code={price_code}")

    currency = (norm(row, "currency") or "aud").lower()
    interval = norm(row, "interval") or "one_time"
    interval_count = to_int_or_none(row.get("interval_count")) or 1

    md_base = {
        "price_code": price_code,
        "pack_qty": norm(row, "pack_qty"),
        "sessions_per_day": norm(row, "sessions_per_day"),
        "visits_per_week": norm(row, "visits_per_week"),
        "service_code": norm(row, "service_code", "metadata.service_code"),
        "billing": norm(row, "billing", "metadata.billing"),
        "plan": norm(row, "plan", "metadata.plan"),
    }
    metadata = clean_meta(md_base | {k: v for k, v in row.items() if k.startswith("metadata.")})

    existing_id = find_price_by_code(price_code)
    if existing_id:
        old_amount = get_price_amount(existing_id)
        if old_amount == amount:
            stripe.Price.modify(existing_id, nickname=nickname or None, metadata=metadata)
            return existing_id
        else:
            archive_price(existing_id)

    create_params = {
        "product": product_id,
        "unit_amount": amount,
        "currency": currency,
        "nickname": nickname or None,
        "metadata": metadata,
    }
    if interval.lower() != "one_time":
        create_params["recurring"] = {"interval": interval.lower(), "interval_count": int(interval_count)}

    pr = stripe.Price.create(**create_params)
    return pr.id

def main(products_csv: str | None, prices_csv: str | None):
    stripe.api_key = get_stripe_key()
    if not stripe.api_key:
        die("Stripe key missing in secrets_config.py")

    if not products_csv and not prices_csv:
        die("Usage: python tools/import_from_csv.py <products_csv or ''> <prices_csv or ''>")

    product_id_by_name: dict[str, str] = {}

    if products_csv:
        if not os.path.exists(products_csv):
            die(f"Products CSV not found: {products_csv}")
        for r in read_csv(products_csv):
            pid = upsert_product(r)
            pname = norm(r, "product_name", "name")
            product_id_by_name[pname] = pid
            print(f"Product OK: {pname} -> {pid}")

    if prices_csv:
        if not os.path.exists(prices_csv):
            die(f"Prices CSV not found: {prices_csv}")
        for r in read_csv(prices_csv):
            pname = norm(r, "product_name", "name", "product_lookup")
            pid = product_id_by_name.get(pname) or find_product_by_name(pname)
            if not pid:
                die(f"Price row refers to unknown product '{pname}'. Make sure Products were imported first.")
            pr_id = upsert_price(r, pid)
            label = norm(r, "price_nickname", "nickname") or "(no nickname)"
            pcode = norm(r, "price_code")
            print(f"Price OK: {label} ({pcode}) -> {pr_id}")

    print("\nAll done. Products & Prices are synced from CSVs.")

if __name__ == "__main__":
    argv = sys.argv[1:]
    products_csv = argv[0] if len(argv) >= 1 and argv[0].strip() != "" else None
    prices_csv   = argv[1] if len(argv) >= 2 and argv[1].strip() != "" else None
    main(products_csv, prices_csv)
