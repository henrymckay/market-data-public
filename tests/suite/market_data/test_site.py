import datetime
import json

import duckdb
import polars
import pytest
import typer.testing

from market_data.code import operate, port, transform
from market_data.code.adapt import motherduck, site
from market_data.code.drive import cli
from pytest_ import fake


def _days(count: int) -> list[datetime.date]:
    start = datetime.date(2026, 1, 5)
    return [start + datetime.timedelta(days=offset) for offset in range(count)]


@pytest.fixture
def site_bars(make_bars):
    rows = [
        ("AAA", day, {"adj_close": 100.0 + i, "close": 100.0 + i})
        for i, day in enumerate(_days(70))
    ]
    rows += [("^TNX", day, {"adj_close": 4.0, "close": 4.0}) for day in _days(5)]
    return make_bars(*rows)


@pytest.fixture
def site_metrics(site_bars):
    return transform.build_metrics(site_bars)


@pytest.fixture
def no_rejections():
    return polars.DataFrame(
        {"ticker": ["AAA"], "rejected": [2]},
        schema={"ticker": polars.String, "rejected": polars.Int64},
    )


@pytest.fixture
def overview(small_universe, site_metrics, site_bars, no_rejections):
    return transform.build_overview(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        tickers=small_universe,
    )


@pytest.mark.parametrize(
    ("ticker", "slug"),
    [
        ("^GSPC", "gspc"),
        ("EURUSD=X", "eurusdx"),
        ("BRK.B", "brkb"),
        ("BTC-USD", "btc-usd"),
    ],
)
def test_when_slugging_then_symbols_are_lowercased_without_punctuation(ticker, slug):
    assert transform.slug(ticker) == slug


def test_when_overview_built_then_one_row_per_instrument_in_ticker_order(overview):
    assert overview.get_column("ticker").to_list() == ["AAA", "BBB", "^TNX"]


def test_when_overview_built_then_metrics_are_columns_with_their_values(overview):
    row = overview.filter(polars.col("ticker") == "AAA").row(0, named=True)
    assert row["last_close"] == 169.0
    assert row["return_1d"] == pytest.approx(169 / 168 - 1)


def test_when_overview_built_then_spark_is_the_last_63_adjusted_closes(overview):
    spark = overview.filter(polars.col("ticker") == "AAA").row(0, named=True)["spark"]
    assert spark == [float(100 + i) for i in range(7, 70)]


def test_when_history_is_short_then_spark_holds_every_bar(overview):
    row = overview.filter(polars.col("ticker") == "^TNX").row(0, named=True)
    assert len(row["spark"]) == 5


def test_when_overview_built_then_coverage_columns_are_stated(overview):
    row = overview.filter(polars.col("ticker") == "AAA").row(0, named=True)
    assert (row["first_day"], row["last_day"]) == (_days(70)[0], _days(70)[-1])
    assert (row["bar_count"], row["rejected"], row["slug"]) == (70, 2, "aaa")


def test_when_an_instrument_has_no_bars_then_it_stays_with_nulls_and_zero_count(
    overview,
):
    row = overview.filter(polars.col("ticker") == "BBB").row(0, named=True)
    assert (row["bar_count"], row["rejected"], row["last_close"]) == (0, 0, None)
    assert row["spark"] is None


def test_when_a_return_is_absent_then_its_column_is_null_not_missing(overview):
    assert "return_5y" in overview.columns


def test_when_export_runs_then_every_site_file_is_written(
    small_universe, site_bars, site_metrics, no_rejections, tmp_path
):
    source = fake.Source(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        runs=fake.runs_frame(),
        tickers=small_universe,
    )

    written = operate.export_site(source, writer=site.Writer(tmp_path))

    names = sorted(file.path for file in written)
    assert names == [
        "bars/aaa.parquet",
        "bars/tnx.parquet",
        "latest.json",
        "overview.parquet",
        "runs.parquet",
    ]
    assert polars.read_parquet(tmp_path / "overview.parquet").height == 3
    assert polars.read_parquet(tmp_path / "bars" / "aaa.parquet").height == 70


def test_when_export_runs_then_bars_files_omit_ticker_and_fetched(
    small_universe, site_bars, site_metrics, no_rejections, tmp_path
):
    source = fake.Source(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        runs=fake.runs_frame(),
        tickers=small_universe,
    )
    operate.export_site(source, writer=site.Writer(tmp_path))

    columns = polars.read_parquet(tmp_path / "bars" / "aaa.parquet").columns
    assert columns == [
        "adj_close",
        "close",
        "day",
        "dividend",
        "high",
        "low",
        "open",
        "split",
        "volume",
    ]


def test_when_latest_written_then_it_holds_the_last_stored_yahoo_run(
    small_universe, site_bars, site_metrics, no_rejections, tmp_path
):
    source = fake.Source(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        runs=fake.runs_frame(),
        tickers=small_universe,
    )
    operate.export_site(source, writer=site.Writer(tmp_path))

    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest == {
        "day": "2026-11-16",
        "ended": "2026-11-17T02:19:41Z",
        "outcome": "stored",
        "rows": 803114,
    }


def test_when_runs_exceed_90_then_only_the_last_90_are_written(
    small_universe, site_bars, site_metrics, no_rejections, tmp_path
):
    source = fake.Source(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        runs=fake.runs_frame(count=120),
        tickers=small_universe,
    )
    operate.export_site(source, writer=site.Writer(tmp_path))

    runs = polars.read_parquet(tmp_path / "runs.parquet")
    assert runs.height == 90
    assert runs.get_column("ended").is_sorted(descending=True)


def test_when_there_are_no_runs_then_latest_is_null(
    small_universe, site_bars, site_metrics, no_rejections, tmp_path
):
    source = fake.Source(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        runs=fake.runs_frame(count=0),
        tickers=small_universe,
    )
    operate.export_site(source, writer=site.Writer(tmp_path))

    assert json.loads((tmp_path / "latest.json").read_text()) is None


def test_when_parquet_is_written_then_it_is_snappy(
    small_universe, site_bars, site_metrics, no_rejections, tmp_path
):
    source = fake.Source(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        runs=fake.runs_frame(),
        tickers=small_universe,
    )
    operate.export_site(source, writer=site.Writer(tmp_path))

    import pyarrow.parquet

    meta = pyarrow.parquet.ParquetFile(tmp_path / "overview.parquet").metadata
    assert meta.row_group(0).column(0).compression == "SNAPPY"


@pytest.fixture
def seeded(tmp_path, site_bars, small_universe):
    path = str(tmp_path / "market.duckdb")
    connection = motherduck.connect(path)
    store = motherduck.Store(connection)
    stamp = datetime.datetime(2026, 11, 17, 2, 17, tzinfo=datetime.UTC)
    store.replace(
        port.Load(
            answered=("AAA", "^TNX"),
            bars=site_bars,
            fetched=stamp,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=small_universe,
        )
    )
    metrics = transform.build_metrics(site_bars)
    store.replace_metrics(
        metrics,
        transform.build_overview(
            bars=site_bars,
            metrics=metrics,
            rejected=store.read_rejected_counts(),
            tickers=store.read_tickers(),
        ),
    )
    connection.close()
    return path


def test_when_exporting_a_local_store_then_csv_rows_name_each_file(
    seeded, tmp_path, monkeypatch
):
    monkeypatch.setenv("MARKET_DATA_DATABASE", seeded)
    monkeypatch.delenv("motherduck_token", raising=False)
    out = tmp_path / "site"

    result = typer.testing.CliRunner().invoke(cli.app, ["export", "--output", str(out)])

    lines = result.stdout.splitlines()
    assert result.exit_code == 0
    assert lines[0] == "path,rows,bytes"
    assert {line.split(",")[0] for line in lines[1:]} == {
        "bars/aaa.parquet",
        "bars/tnx.parquet",
        "latest.json",
        "overview.parquet",
        "runs.parquet",
    }
    assert duckdb.connect().execute(
        "select count(*) from read_parquet(?)", [str(out / "overview.parquet")]
    ).fetchone() == (3,)
