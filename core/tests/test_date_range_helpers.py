import pytest
from core.date_range_helpers import parse_label
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Australia/Brisbane")

@pytest.mark.parametrize("label", [
  "this-week","next-week","two-weeks","four-weeks","this-month","next-month","month-after","next-3-months"
])
def test_presets_do_not_crash(label):
    s, e = parse_label(label)
    assert s.tzinfo is not None and e.tzinfo is not None

def test_custom_range_params():
    s, e = parse_label("custom", start_param="2025-09-01", end_param="2025-09-10")
    assert str(s.date()) == "2025-09-01"
    assert str(e.date()) == "2025-09-11"  # End date is inclusive, so adds 1 day