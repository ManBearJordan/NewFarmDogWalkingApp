from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class APIServiceInfoTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client = Client()
        self.client.login(username="testuser", password="testpass")

    def test_api_service_info_returns_price(self):
        url = reverse("api_service_info")
        resp = self.client.get(url, {"service_label": "Dog Walk"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should include canonical fields and an integer price (or None if catalog lacks it)
        self.assertIn("service_label", data)
        self.assertIn("service_code", data)
        self.assertIn("price_cents", data)
        self.assertIsInstance(data["price_cents"], (int, type(None)))