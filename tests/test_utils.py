import pytest

from src.utils import retry


def test_retry_succeeds_first_try():
    call_count = 0

    @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
    def succeeds():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = succeeds()
    assert result == "ok"
    assert call_count == 1


def test_retry_succeeds_after_failure():
    call_count = 0

    @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
    def fails_then_succeeds():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("not yet")
        return "ok"

    result = fails_then_succeeds()
    assert result == "ok"
    assert call_count == 3


def test_retry_raises_after_max_attempts():
    @retry(max_attempts=2, delay=0.01, exceptions=(ValueError,))
    def always_fails():
        raise ValueError("fail")

    with pytest.raises(ValueError, match="fail"):
        always_fails()


def test_retry_does_not_catch_unspecified_exceptions():
    @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
    def raises_type_error():
        raise TypeError("wrong type")

    with pytest.raises(TypeError, match="wrong type"):
        raises_type_error()
