"""The monitor's rules: every parameter, validated once and hashed into each signal."""

import hashlib
import json
import typing

import pydantic

from market_data.code import error

type Timeframe = typing.Literal["d", "w", "m"]
type Grade = typing.Literal["A", "B", "C"]
type Event = typing.Literal[
    "break_up", "confirm_up", "fail_up", "break_down", "confirm_down", "fail_down"
]

TIMEFRAMES: tuple[Timeframe, ...] = ("d", "w", "m")

_HASH_DIGITS = 12


def _kebab(name: str) -> str:
    """Return a field name as the YAML spells it, with hyphens."""
    return name.rstrip("_").replace("_", "-")


class _Model(pydantic.BaseModel):
    """A frozen model that reads hyphenated keys and refuses unknown ones."""

    model_config = pydantic.ConfigDict(
        alias_generator=_kebab, extra="forbid", frozen=True
    )


class PerTimeframe[T](_Model):
    """One value for each timeframe."""

    d: T
    m: T
    w: T

    def at(self, timeframe: str) -> T:
        """Return the value for `d`, `w` or `m`."""
        return getattr(self, timeframe)


class AtLeast(_Model):
    """A point given when a figure reaches a bound."""

    at_least: pydantic.PositiveFloat
    points: pydantic.NonNegativeInt


class Margin(_Model):
    """Points for a signal's margin, with a bound per kind of event."""

    break_: pydantic.PositiveFloat
    confirm: pydantic.PositiveFloat
    points: pydantic.NonNegativeInt


class Score(_Model):
    """The points that make a grade."""

    aligned: pydantic.NonNegativeInt
    margin_atr: Margin
    timeframe: PerTimeframe[pydantic.NonNegativeInt]
    trend_swings: AtLeast
    volume_ratio: AtLeast


class Grades(_Model):
    """The least score of grade A and of grade B."""

    A: pydantic.PositiveInt
    B: pydantic.PositiveInt

    @pydantic.model_validator(mode="after")
    def _check_order(self) -> typing.Self:
        """Require A above B."""
        if self.A <= self.B:
            raise ValueError("A must be above B")
        return self


class Alerts(_Model):
    """What is sent, read by the notify stage."""

    base_rate_min_n: pydantic.PositiveInt
    digest_grade: Grade
    events: tuple[Event, ...]
    muted_asset_classes: tuple[str, ...]
    push_cap: pydantic.PositiveInt
    push_grade: Grade
    site_url: str
    window_days: pydantic.PositiveInt


class Rules(_Model):
    """Every parameter of the monitor."""

    alerts: Alerts
    atr_bars: pydantic.PositiveInt
    grades: Grades
    horizons: PerTimeframe[tuple[pydantic.PositiveInt, ...]]
    score: Score
    swing_atr: PerTimeframe[pydantic.PositiveFloat]


def parse_rules(document: object) -> Rules:
    """Validate a parsed YAML document as the rules.

    :param document: The mapping `yaml.safe_load` returned.
    :returns: The rules.
    :raises ConfigurationError: Naming the first key that is missing or invalid.
    """
    try:
        return Rules.model_validate(document)
    except pydantic.ValidationError as failure:
        first = failure.errors()[0]
        key = ".".join(str(part) for part in first["loc"])
        raise error.ConfigurationError(
            f"The rules file is invalid at '{key}': {first['msg']}"
        ) from None


def hash_rules(rules: Rules) -> str:
    """Return the first 12 hex digits of the SHA-256 of the rules' canonical JSON."""
    canonical = json.dumps(
        rules.model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:_HASH_DIGITS]
