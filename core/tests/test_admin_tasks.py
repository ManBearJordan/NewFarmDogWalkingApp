import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from zoneinfo import ZoneInfo
from core.models import AdminEvent

TZ = ZoneInfo("Australia/Brisbane")

@pytest.fixture
def authed(client):
    u = User.objects.create_user(username="u", password="p", is_staff=True)
    client.login(username="u", password="p")
    return client

@pytest.mark.django_db
def test_admin_tasks_crud_and_filters(authed):
    now = timezone.now().astimezone(TZ)
    # Create
    resp = authed.post(reverse("admin_task_create"), {
        "due_dt": now.strftime("%Y-%m-%d %H:%M:%S"),
        "title": "Call vet",
        "notes": "Follow-up on vaccine"
    }, follow=True)
    assert resp.status_code == 200
    ev = AdminEvent.objects.get(title="Call vet")
    # Edit
    resp = authed.post(reverse("admin_task_edit", args=[ev.id]), {
        "due_dt": now.strftime("%Y-%m-%d %H:%M:%S"),
        "title": "Call clinic",
        "notes": "Updated"
    }, follow=True)
    assert resp.status_code == 200
    ev.refresh_from_db()
    assert ev.title == "Call clinic"
    # List upcoming
    html = authed.get(reverse("admin_tasks_list")).content.decode()
    assert "Call clinic" in html
    # List past
    ev.due_dt = now.replace(year=now.year - 1)
    ev.save(update_fields=["due_dt"])
    html = authed.get(reverse("admin_tasks_list") + "?f=past").content.decode()
    assert "Call clinic" in html
    # Delete
    resp = authed.post(reverse("admin_task_delete", args=[ev.id]), follow=True)
    assert resp.status_code == 200
    assert AdminEvent.objects.count() == 0