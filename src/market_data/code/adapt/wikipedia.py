# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Read the S&P 500's members from Wikipedia's list."""

import io
import urllib.request

import pandas
import polars

from market_data.code import error

_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_USER_AGENT = "Mozilla/5.0 (compatible; market-data-universe-sync)"
_TIMEOUT_SECONDS = 30
_COLUMNS = {"GICS Sector": "sector", "Security": "name", "Symbol": "symbol"}


def parse_members(page: str) -> polars.DataFrame:
    """Return the members table of the list's HTML page.

    :param page: The page's HTML.
    :returns: `symbol`, `name` and `sector`, one row per member, as published.
    :raises SourceError: If the page holds no members table with those columns.
    """
    try:
        table = pandas.read_html(
            io.StringIO(page), attrs={"id": "constituents"}, flavor="lxml"
        )[0]
        return (
            polars.DataFrame(table[list(_COLUMNS)])
            .rename(_COLUMNS)
            .select("symbol", "name", "sector")
            .cast(polars.String)
        )
    except (ValueError, KeyError, IndexError) as failure:
        raise error.SourceError("The S&P 500 list has no members table") from failure


def fetch_members() -> polars.DataFrame:
    """Fetch the S&P 500's members from Wikipedia.

    :returns: `symbol`, `name` and `sector`, one row per member, as published.
    :raises SourceError: If Wikipedia does not answer or the page is not the list.
    """
    request = urllib.request.Request(_URL, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            page = response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as failure:
        raise error.SourceError("Wikipedia's S&P 500 list did not answer") from failure
    return parse_members(page)
