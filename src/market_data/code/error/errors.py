"""Error classes every layer raises."""


class ConfigurationError(Exception):
    """A setting is missing or refused, so no run can start (exit code 2)."""


class SourceError(Exception):
    """A source answered nothing usable, so nothing was changed (exit code 1)."""


class StoreError(Exception):
    """The store failed while loading or reading (exit code 1)."""
