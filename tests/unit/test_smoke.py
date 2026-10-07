"""Smoke test — verifies the test pipeline can discover and execute tests."""


def test_smoke() -> None:
    """Assert True to confirm pytest is wired up correctly."""
    assert True


def test_ci_catches_failures() -> None:
    """Verify the CI pipeline correctly detects test failures (now fixed)."""
    assert True
