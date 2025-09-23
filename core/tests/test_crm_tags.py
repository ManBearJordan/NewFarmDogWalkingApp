import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Client, Tag

@pytest.fixture
def authed(client):
    u = User.objects.create_user(username="u", password="p")
    client.login(username="u", password="p")
    return client

@pytest.mark.django_db
def test_tag_crud_and_assign_to_client(authed):
    # Create tag
    authed.post(reverse("tag_create"), {"name": "VIP", "color": "#ff9900"})
    t = Tag.objects.get(name="VIP")
    # Create client with tag
    resp = authed.post(reverse("client_create"), {
        "name": "Alice",
        "email": "",
        "phone": "",
        "address": "",
        "notes": "",
        "tags": [t.id],
    }, follow=True)
    assert resp.status_code == 200
    c = Client.objects.get(name="Alice")
    assert list(c.tags.values_list("name", flat=True)) == ["VIP"]
    # Edit tag
    authed.post(reverse("tag_edit", args=[t.id]), {"name": "VVIP", "color": ""})
    assert Tag.objects.filter(name="VVIP").exists()
    # Delete tag
    authed.post(reverse("tag_delete", args=[t.id]), follow=True)
    assert Tag.objects.count() == 0