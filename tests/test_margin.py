"""OWNER: A. Rule tests for engine/margin.py. Un-skip as each rule is implemented."""
import pytest


@pytest.mark.skip(reason="TODO(A): needs fixture accounts")
def test_below_soft_edge_is_immediate():
    ...


@pytest.mark.skip(reason="TODO(A)")
def test_below_maintenance_over_48h_is_anytime():
    ...


@pytest.mark.skip(reason="TODO(A)")
def test_friday_uplift_raises_soft_edge():
    ...
