import pytest
from django.core.exceptions import ValidationError
from core.credit import get_client_credit, add_client_credit, deduct_client_credit
from core.models import Client

@pytest.mark.django_db
def test_client_id_vs_instance_functionality():
    """Test that functions work with both client instances and IDs."""
    c = Client.objects.create(name="ID Test Client", credit_cents=1000)
    
    # Test with client instance
    assert get_client_credit(c) == 1000
    new_bal = add_client_credit(c, 500)
    assert new_bal == 1500
    assert get_client_credit(c) == 1500
    
    # Test with client ID
    assert get_client_credit(c.id) == 1500
    new_bal2 = deduct_client_credit(c.id, 300)
    assert new_bal2 == 1200
    
    # Refresh and verify
    c.refresh_from_db()
    assert c.credit_cents == 1200

@pytest.mark.django_db
def test_deduct_credit_validation():
    """Test deduct_client_credit validation and edge cases."""
    c = Client.objects.create(name="Deduct Test Client", credit_cents=1000)
    
    # Test normal deduction
    result = deduct_client_credit(c, 400)
    assert result == 600
    
    # Test zero/negative amounts (should be no-op)
    result = deduct_client_credit(c, 0)
    assert result == 600
    result = deduct_client_credit(c, -100)
    assert result == 600
    
    # Test overdraft prevention
    with pytest.raises(ValidationError, match="Insufficient credit"):
        deduct_client_credit(c, 700)  # More than remaining 600
        
    # Verify client credit unchanged after failed deduction
    c.refresh_from_db()
    assert c.credit_cents == 600

@pytest.mark.django_db 
def test_add_credit_negative_flags():
    """Test add_client_credit with negative amounts and allow_negative flag."""
    c = Client.objects.create(name="Negative Test Client", credit_cents=1000)
    
    # Test negative without flag (should fail)
    with pytest.raises(ValidationError, match="Credit cannot go negative"):
        add_client_credit(c, -1200)  # Would make it negative
        
    # Test negative with flag (should work)
    result = add_client_credit(c, -300, allow_negative=True)
    assert result == 700
    
    # Test going negative with flag
    result = add_client_credit(c, -800, allow_negative=True)
    assert result == -100
    c.refresh_from_db()
    assert c.credit_cents == -100