import pytest

from market_data.code import transform


@pytest.mark.parametrize(
    ("answered", "failed_items", "tolerance", "outcome"),
    [
        (90, 0, 0, transform.Outcome.STORED),
        (89, 1, 0, transform.Outcome.PARTIAL),
        (89, 1, 1, transform.Outcome.STORED),
        (0, 90, 0, transform.Outcome.FAILED),
        (0, 90, 100, transform.Outcome.FAILED),
    ],
)
def test_when_judge_outcome_then_outcome_follows_answers_and_tolerance(
    answered, failed_items, tolerance, outcome
):
    judged = transform.judge_outcome(
        answered=answered, failed_items=failed_items, tolerance=tolerance
    )

    assert judged is outcome


def test_when_active_tickers_then_inactive_rows_are_skipped(small_universe):
    import polars

    paused = small_universe.with_columns(active=polars.col("ticker").ne("BBB"))

    assert transform.active_tickers(paused) == ["AAA", "^TNX"]
