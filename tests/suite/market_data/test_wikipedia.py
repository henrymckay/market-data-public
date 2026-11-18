import pathlib

import pytest

from market_data.code import error
from market_data.code.adapt import wikipedia

_PAGE = pathlib.Path(__file__).parents[2] / "data" / "wikipedia" / "constituents.html"


def test_when_parse_members_then_the_constituents_table_maps_to_three_columns():
    members = wikipedia.parse_members(_PAGE.read_text())

    assert members.columns == ["symbol", "name", "sector"]
    assert members.get_column("symbol").to_list() == ["MMM", "BRK.B", "AAPL"]
    assert members.row(2) == ("AAPL", "Apple Inc.", "Information Technology")


def test_when_the_page_has_no_constituents_table_then_parse_members_fails():
    with pytest.raises(error.SourceError):
        wikipedia.parse_members("<html><table id='other'><tr><td>1</td></tr></table>")
