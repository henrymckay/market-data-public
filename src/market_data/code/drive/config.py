"""Settings, read once from the environment at the composition root."""

import os

import pydantic
import pydantic_settings

from market_data.code import error


class Settings(pydantic_settings.BaseSettings):
    """Where the store is, and whether the token for MotherDuck is present."""

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="MARKET_DATA_", extra="ignore"
    )

    database: str = "md:market_data"
    motherduck_token: pydantic.SecretStr | None = pydantic.Field(
        default=None, validation_alias="motherduck_token", repr=False
    )


def read_settings() -> Settings:
    """Read the settings and check that a MotherDuck store has its token.

    :returns: The settings.
    :raises ConfigurationError: If a setting is invalid or the token is not set.
    """
    try:
        settings = Settings()
    except pydantic.ValidationError:
        raise error.ConfigurationError("The settings are invalid") from None
    if settings.database.startswith("md:") and settings.motherduck_token is None:
        raise error.ConfigurationError("motherduck_token is not set")
    return settings


def read_token_for_redaction() -> str | None:
    """Return the token's value from the environment, for the log's redaction only."""
    return os.environ.get("motherduck_token") or None  # noqa: SIM112
