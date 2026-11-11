from datetime import timedelta

import pytest

from apps.accounts.otp import OtpLocked, issue_code, verify_code


def test_code_expires_after_5_minutes(db, freezer):
    issue_code("+77011234567")
    freezer.tick(timedelta(minutes=5, seconds=1))
    assert verify_code("+77011234567", "0000") is False


def test_locked_after_5_wrong_attempts(db):
    issue_code("+77011234567")
    for _ in range(5):
        assert verify_code("+77011234567", "1111") is False
    with pytest.raises(OtpLocked):
        verify_code("+77011234567", "0000")


def test_fixed_demo_code_accepted_once(db):
    issue_code("+77011234567")
    assert verify_code("+77011234567", "0000") is True
    assert verify_code("+77011234567", "0000") is False
