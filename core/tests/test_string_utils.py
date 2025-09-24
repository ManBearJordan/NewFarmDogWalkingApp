from core.templatetags.string_utils import split

def test_split_filter_default_separator():
    # Test the split filter with default separator ":"
    result = split("a:b:c")
    assert result == ["a", "b", "c"]

def test_split_filter_custom_separator():
    # Test the split filter with custom separator
    result = split("a,b,c", ",")
    assert result == ["a", "b", "c"]