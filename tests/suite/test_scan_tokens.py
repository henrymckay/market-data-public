import importlib.util
import pathlib

import pytest

_PATH = pathlib.Path(__file__).parents[2] / "scripts" / "scan_tokens.py"
_SPEC = importlib.util.spec_from_file_location("scan_tokens", _PATH)
assert _SPEC
assert _SPEC.loader
scan = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scan)

SECRET = "abcdefghijklmnopqrstuvwxyz.0123456789ABCDEF.tail-of-the-token"


def test_when_a_log_holds_a_fragment_then_it_is_counted_and_exit_is_1(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TOKEN", SECRET)
    (tmp_path / "run.log").write_text(f"leak: {SECRET[3:25]} here")

    code = scan.main([str(tmp_path), "TOKEN"])

    assert code == 1
    assert "whole 0, fragments" in capsys.readouterr().out


def test_when_a_log_holds_the_whole_value_then_it_is_counted(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TOKEN", SECRET)
    (tmp_path / "run.log").write_text(f"x {SECRET} y")

    code = scan.main([str(tmp_path), "TOKEN"])

    assert code == 1
    assert "TOKEN: whole 1" in capsys.readouterr().out


def test_when_the_logs_are_clean_then_exit_is_0(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOKEN", SECRET)
    (tmp_path / "run.log").write_text("::add-mask:: *** nothing here")

    assert scan.main([str(tmp_path), "TOKEN"]) == 0


def test_when_a_variable_is_unset_then_exit_is_2(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TOKEN", raising=False)

    assert scan.main([str(tmp_path), "TOKEN"]) == 2
