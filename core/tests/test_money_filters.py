from django.test import TestCase
from core.templatetags.money_filters import cents_to_dollars, dollars

class MoneyFiltersNewTest(TestCase):
    """Test the new money formatting filters."""

    def test_cents_to_dollars_basic(self):
        self.assertEqual(cents_to_dollars(0), "$0.00")
        self.assertEqual(cents_to_dollars(2500), "$25.00")
        self.assertEqual(cents_to_dollars(None), "—")
        self.assertEqual(cents_to_dollars("bad"), "—")

    def test_dollars_filter(self):
        self.assertEqual(dollars(25), "$25.00")
        self.assertEqual(dollars(25.5), "$25.50")
        self.assertEqual(dollars(None), "—")