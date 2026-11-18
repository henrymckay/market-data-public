import pytest
import yaml

from market_data.code import error, transform
from market_data.code.adapt import rules as rules_adapter


def _document():
    return yaml.safe_load(
        rules_adapter.resources.files("market_data")
        .joinpath("data/transform/monitor.yaml")
        .read_text()
    )


def test_when_the_packaged_rules_are_read_then_they_hold_the_plans_numbers():
    rules = rules_adapter.read_rules()

    assert rules.atr_bars == 14
    assert (rules.swing_atr.d, rules.swing_atr.w, rules.swing_atr.m) == (2.5, 2.0, 2.0)
    assert rules.horizons.w == (4, 13, 26)
    assert (rules.grades.A, rules.grades.B) == (3, 2)
    assert rules.score.margin_atr.break_ == 0.5
    assert rules.alerts.push_cap == 10


def test_when_the_rules_are_hashed_then_the_id_is_12_hex_digits_and_stable():
    first = transform.hash_rules(rules_adapter.read_rules())
    second = transform.hash_rules(transform.parse_rules(_document()))

    assert first == second
    assert len(first) == 12
    int(first, 16)


def test_when_one_threshold_changes_then_the_hash_changes():
    document = _document()
    document["swing-atr"]["d"] = 3.0

    changed = transform.hash_rules(transform.parse_rules(document))

    assert changed != transform.hash_rules(rules_adapter.read_rules())


@pytest.mark.parametrize(
    ("edit", "key"),
    [
        (lambda d: d.pop("atr-bars"), "atr-bars"),
        (lambda d: d["swing-atr"].pop("w"), "swing-atr.w"),
        (lambda d: d["swing-atr"].update(d=0), "swing-atr.d"),
        (lambda d: d["score"]["margin-atr"].pop("break"), "score.margin-atr.break"),
        (lambda d: d["grades"].pop("A"), "grades.A"),
        (lambda d: d["grades"].update(C=1), "grades.C"),
        (lambda d: d.update(surprise=1), "surprise"),
        (lambda d: d["alerts"].update({"push-grade": "Z"}), "alerts.push-grade"),
    ],
)
def test_when_a_key_is_missing_or_invalid_then_the_error_names_it(edit, key):
    document = _document()
    edit(document)

    with pytest.raises(error.ConfigurationError, match=key):
        transform.parse_rules(document)


def test_when_grade_a_is_not_above_b_then_the_rules_are_refused():
    document = _document()
    document["grades"] = {"A": 2, "B": 2}

    with pytest.raises(error.ConfigurationError, match="grades"):
        transform.parse_rules(document)


def test_when_the_file_is_missing_or_not_yaml_then_a_configuration_error(tmp_path):
    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [unclosed")

    with pytest.raises(error.ConfigurationError):
        rules_adapter.read_rules(tmp_path / "absent.yaml")
    with pytest.raises(error.ConfigurationError):
        rules_adapter.read_rules(broken)
