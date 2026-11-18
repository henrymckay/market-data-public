"""Read the monitor's rules from the package's YAML, or from a file."""

import pathlib
from importlib import resources

import yaml

from market_data.code import error, transform


def read_rules(path: pathlib.Path | None = None) -> transform.Rules:
    """Return the rules in `path`, or the packaged ones.

    :param path: Another rules file, or none for `monitor.yaml`.
    :returns: The validated rules.
    :raises ConfigurationError: If the file is unreadable, not YAML or invalid.
    """
    try:
        text = (
            path.read_text()
            if path is not None
            else resources.files("market_data")
            .joinpath("data/transform/monitor.yaml")
            .read_text()
        )
        document: object = yaml.safe_load(text)
    except (OSError, yaml.YAMLError) as failure:
        raise error.ConfigurationError(
            f"The rules file cannot be read: {failure}"
        ) from None
    return transform.parse_rules(document)
