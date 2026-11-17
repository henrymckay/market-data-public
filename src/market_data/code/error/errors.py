"""Error classes every layer raises."""


class ConfigurationError(Exception):
    """A setting is missing or refused, so no run can start (exit code 2)."""


class StoreError(Exception):
    """The store failed while loading or reading (exit code 1)."""
