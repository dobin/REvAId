"""D34a: `is_utility` predicate boundary behaviour."""

from __future__ import annotations

from graphrev.classification.utility import is_utility


def test_fan_in_equal_to_threshold_is_not_utility() -> None:
    assert is_utility(fan_in=50, threshold=50) is False


def test_fan_in_one_over_threshold_is_utility() -> None:
    assert is_utility(fan_in=51, threshold=50) is True


def test_fan_in_zero_with_zero_threshold_is_not_utility() -> None:
    assert is_utility(fan_in=0, threshold=0) is False


def test_fan_in_far_below_threshold_is_not_utility() -> None:
    assert is_utility(fan_in=1, threshold=50) is False


def test_fan_in_far_above_threshold_is_utility() -> None:
    assert is_utility(fan_in=291, threshold=50) is True
