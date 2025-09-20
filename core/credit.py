"""Client credit management helpers."""
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Client


def get_client_credit(client: Client) -> int:
    """Get the current credit balance for a client in cents.
    
    Args:
        client: Client model instance
        
    Returns:
        int: Credit balance in cents
    """
    return client.credit_cents


def use_client_credit(client: Client, amount_cents: int) -> None:
    """Use client credit atomically, preventing negative balances.
    
    Args:
        client: Client model instance
        amount_cents: Amount to deduct in cents
        
    Raises:
        ValidationError: If amount_cents would result in negative balance
        ValueError: If amount_cents is negative or not an integer
    """
    if not isinstance(amount_cents, int):
        raise ValueError("amount_cents must be an integer")
    
    if amount_cents < 0:
        raise ValueError("amount_cents must be non-negative")
    
    if amount_cents == 0:
        return  # No-op for zero amount
    
    with transaction.atomic():
        # Lock the client record to prevent race conditions
        locked_client = Client.objects.select_for_update().get(id=client.id)
        
        if locked_client.credit_cents < amount_cents:
            raise ValidationError(
                f"Insufficient credit. Available: {locked_client.credit_cents} cents, "
                f"Requested: {amount_cents} cents"
            )
        
        # Deduct the credit
        locked_client.credit_cents -= amount_cents
        locked_client.save(update_fields=['credit_cents'])
        
        # Update the original client instance to reflect the change
        client.credit_cents = locked_client.credit_cents