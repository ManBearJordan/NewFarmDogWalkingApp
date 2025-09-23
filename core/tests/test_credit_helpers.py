import pytest
from django.core.exceptions import ValidationError
from core.credit import get_client_credit, add_client_credit, deduct_client_credit
from core.models import Client

@pytest.mark.django_db
def test_add_and_deduct_credit_happy_path():
    c = Client.objects.create(name="Alice", credit_cents=0)
    bal = add_client_credit(c, 2500)
    assert bal == 2500
    assert get_client_credit(c) == 2500
    bal2 = deduct_client_credit(c, 1500)
    assert bal2 == 1000
    assert get_client_credit(c.id) == 1000

@pytest.mark.django_db
def test_negative_adjustment_requires_flag():
    c = Client.objects.create(name="Bob", credit_cents=1000)
    with pytest.raises(ValidationError):
        add_client_credit(c, -1500)  # not allowed → would go negative
    # Allowed with flag if result stays >= 0 or you explicitly allow_negative
    bal = add_client_credit(c, -500, allow_negative=True)
    assert bal == 500

@pytest.mark.django_db
def test_deduct_prevents_overdraft():
    c = Client.objects.create(name="Carol", credit_cents=600)
    with pytest.raises(ValidationError):
        deduct_client_credit(c, 700)