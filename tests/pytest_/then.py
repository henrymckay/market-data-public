"""Assertions that name a claim about the domain."""

import polars


def conserves(*, kept: polars.DataFrame, rejected: polars.DataFrame, sent: int) -> None:
    """Assert that every row sent is either kept or rejected."""
    assert kept.height + rejected.height == sent
