from pdf2zh.casting import safe_int, safe_float


def test_safe_int_valid_string():
    assert safe_int("123") == 123


def test_safe_int_valid_integer():
    assert safe_int(123) == 123


def test_safe_int_valid_float_string():
    assert safe_int("123.45") is None


def test_safe_int_invalid_string():
    assert safe_int("abc") is None


def test_safe_int_none():
    assert safe_int(None) is None


def test_safe_int_boolean():
    assert safe_int(True) == 1
    assert safe_int(False) == 0


def test_safe_int_special_chars():
    assert safe_int("!@#") is None


def test_safe_float_valid_float():
    assert safe_float("123.45") == 123.45


def test_safe_float_valid_integer_string():
    assert safe_float("123") == 123.0


def test_safe_float_scientific_notation():
    assert safe_float("1.23e-4") == 0.000123


def test_safe_float_invalid_string():
    assert safe_float("abc") is None


def test_safe_float_none():
    assert safe_float(None) is None


def test_safe_float_boolean():
    assert safe_float(True) == 1.0
    assert safe_float(False) == 0.0


def test_safe_float_special_chars():
    assert safe_float("!@#") is None
