"""The export use case: shape the stored tables into the dashboard's files."""

from market_data.code import port, transform


def export_site(
    source: port.SiteSource, *, writer: port.SiteWriter
) -> tuple[port.Written, ...]:
    """Write the overview, each instrument's bars, the runs and the latest run.

    :param source: Where the stored tables are read.
    :param writer: Where the files go.
    :returns: One record per file written.
    """
    bars = source.read_site_bars()
    runs = source.read_runs()
    overview = transform.build_overview(
        bars=bars,
        metrics=source.read_metrics(),
        rejected=source.read_rejected_counts(),
        tickers=source.read_tickers(),
    )
    per_instrument = transform.build_instrument_bars(bars)
    return (
        writer.write_parquet("overview.parquet", overview),
        *(
            writer.write_parquet(f"bars/{transform.slug(ticker)}.parquet", frame)
            for ticker, frame in sorted(per_instrument.items())
        ),
        writer.write_parquet("runs.parquet", transform.build_runs(runs)),
        writer.write_json("latest.json", transform.build_latest(runs)),
    )
