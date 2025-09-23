from __future__ import annotations
from typing import Union, Optional
from django.db import transaction
from django.core.exceptions import ValidationError

def _get_client_instance(client_or_id):
    from .models import Client
    if hasattr(client_or_id, "id"):
        return client_or_id
    return Client.objects.select_for_update().get(id=int(client_or_id))

def get_client_credit(client_or_id) -> int:
    """Return current credit (cents)."""
    from .models import Client
    if hasattr(client_or_id, "id"):
        return int(getattr(client_or_id, "credit_cents", 0) or 0)
    obj = Client.objects.only("credit_cents").get(id=int(client_or_id))
    return int(obj.credit_cents or 0)

@transaction.atomic
def add_client_credit(client_or_id, amount_cents: int, *, allow_negative: bool=False, reason: Optional[str]=None, by_user=None) -> int:
    """
    Adjust credit by +amount_cents (or negative if allow_negative=True).
    Returns new balance in cents. Prevents going below zero unless allow_negative=True.
    """
    if amount_cents is None:
        raise ValidationError("Amount is required")
    try:
        amount_cents = int(amount_cents)
    except Exception:
        raise ValidationError("Amount must be an integer number of cents")
    c = _get_client_instance(client_or_id)
    current = int(c.credit_cents or 0)
    new_balance = current + amount_cents
    if not allow_negative and new_balance < 0:
        raise ValidationError("Credit cannot go negative")
    c.credit_cents = new_balance
    c.save(update_fields=["credit_cents"])
    # TODO: if you later add a ledger table, record (reason, by_user)
    return new_balance

@transaction.atomic
def deduct_client_credit(client_or_id, amount_cents: int) -> int:
    """
    Deduct exactly amount_cents from credit (must be >= 0 and <= current).
    Returns new balance. No-ops when amount_cents <= 0.
    """
    if not amount_cents or amount_cents <= 0:
        return get_client_credit(client_or_id)
    try:
        amount_cents = int(amount_cents)
    except Exception:
        raise ValidationError("Amount must be cents (integer)")
    c = _get_client_instance(client_or_id)
    current = int(c.credit_cents or 0)
    if amount_cents > current:
        raise ValidationError("Insufficient credit")
    c.credit_cents = current - amount_cents
    c.save(update_fields=["credit_cents"])
    return int(c.credit_cents)