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
    ntfy_topic: pydantic.SecretStr | None = pydantic.Field(
        default=None, validation_alias="NTFY_TOPIC", repr=False
    )
    github_repository: str | None = pydantic.Field(
        default=None, validation_alias="GITHUB_REPOSITORY"
    )
    github_run_id: str | None = pydantic.Field(
        default=None, validation_alias="GITHUB_RUN_ID"
    )
    github_server_url: str | None = pydantic.Field(
        default=None, validation_alias="GITHUB_SERVER_URL"
    )

    @property
    def run_url(self) -> str | None:
        """The Actions run's page, when the job runs on GitHub."""
        if not (
            self.github_server_url and self.github_repository and self.github_run_id
        ):
            return None
        return (
            f"{self.github_server_url}/{self.github_repository}"
            f"/actions/runs/{self.github_run_id}"
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


def read_secrets_for_redaction() -> tuple[str, ...]:
    """Return the token and the topic from the environment, for redaction only."""
    values = (os.environ.get("motherduck_token"), os.environ.get("NTFY_TOPIC"))  # noqa: SIM112
    return tuple(value for value in values if value)
