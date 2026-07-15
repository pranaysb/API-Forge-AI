from app.api.stream import normalize_base_url

def test_relative_url_is_resolved_against_default_host():
    assert normalize_base_url("/api/v3") == "http://127.0.0.1:8001/api/v3"

def test_absolute_http_url_is_untouched():
    assert normalize_base_url("http://example.com/v1") == "http://example.com/v1"

def test_absolute_https_url_is_untouched():
    assert normalize_base_url("https://api.example.com") == "https://api.example.com"
