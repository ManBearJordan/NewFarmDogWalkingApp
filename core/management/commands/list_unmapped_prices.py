from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter
import stripe
from django.core.management.base import BaseCommand
from core.models import StripePriceMap

BRISBANE = ZoneInfo("Australia/Brisbane")


class Command(BaseCommand):
    help = "Scan recent Stripe invoices for Price IDs not mapped to a Service. Prints counts and basic context."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90, help="Look back window (default 90).")
        parser.add_argument("--limit", type=int, default=0, help="Max invoices to scan (0 = all in window).")

    def handle(self, *args, **opts):
        days = opts["days"]
        limit = opts["limit"]
        since = datetime.now(tz=BRISBANE) - timedelta(days=days)
        starting_after = None
        seen = 0
        counter = Counter()
        meta = {}
        while True:
            params = {
                "limit": 100,
                "created": {"gte": int(since.timestamp())},
                "expand": ["data.lines.data", "data.lines.data.price", "data.lines.data.price.product"],
            }
            if starting_after:
                params["starting_after"] = starting_after
            page = stripe.Invoice.list(**params)
            data = getattr(page, "data", []) or []
            for inv in data:
                if limit and seen >= limit:
                    break
                seen += 1
                lines = getattr(inv, "lines", None)
                items = getattr(lines, "data", []) if lines else []
                for li in items:
                    price = getattr(li, "price", None)
                    pid = getattr(price, "id", None)
                    if not pid:
                        continue
                    if StripePriceMap.objects.filter(price_id=pid, active=True).exists():
                        continue
                    counter[pid] += 1
                    prod = getattr(price, "product", None)
                    nickname = getattr(price, "nickname", None) or getattr(li, "description", None)
                    meta[pid] = {
                        "nickname": nickname,
                        "product_id": getattr(prod, "id", None) if prod else None,
                    }
            if limit and seen >= limit:
                break
            if not getattr(page, "has_more", False):
                break
            starting_after = data[-1].id if data else None
        if not counter:
            self.stdout.write(self.style.SUCCESS("All Prices in the window are mapped."))
            return
        self.stdout.write(self.style.WARNING("Unmapped Stripe Prices:"))
        for pid, cnt in counter.most_common():
            m = meta.get(pid, {})
            self.stdout.write(f"- {pid}  x{cnt}  nickname={m.get('nickname')!r}  product={m.get('product_id')}")
        self.stdout.write(self.style.SUCCESS(f"Invoices scanned={seen}, Unmapped unique prices={len(counter)}"))
