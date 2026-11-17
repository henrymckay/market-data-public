"""Record yfinance's raw frames for the parse tests, from the repository root."""

import pathlib

import yfinance

yfinance.config.debug.hide_exceptions = False

FOLDER = pathlib.Path(__file__).parent

for ticker, period in (("AAPL", "2y"), ("EURUSD=X", "1mo")):
    frame = yfinance.Ticker(ticker).history(
        actions=True, auto_adjust=False, interval="1d", period=period
    )
    frame.to_parquet(FOLDER / f"{ticker.lower().replace('=', '')}.parquet")
