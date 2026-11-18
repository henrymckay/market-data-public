"""Generate the ntfy topic once, keep it in the keychain and set it as a secret.

The topic is the only key to the alert channel (PLAN.md, D104), so nothing is
printed: it goes into the macOS keychain under `ntfy-market-monitor` and, on
standard input, into `gh secret set NTFY_TOPIC`.  An existing keychain entry is
left alone unless `--rotate` is given, since a new topic means subscribing again.
Exits 0 when the topic was made, 1 when one exists, 2 when a command failed.
"""

import getpass
import secrets
import subprocess
import sys

SERVICE = "ntfy-market-monitor"
REPOSITORY = "henrymckay/market-data-public"
SECRET = "NTFY_TOPIC"


def exists(user: str) -> bool:
    """Return whether the keychain already holds a topic."""
    found = subprocess.run(
        ["security", "find-generic-password", "-a", user, "-s", SERVICE],
        capture_output=True,
        check=False,
    )
    return found.returncode == 0


def main(argv: list[str]) -> int:
    """Make the topic, store it in the keychain and set the repository secret."""
    user = getpass.getuser()
    if exists(user) and "--rotate" not in argv:
        print("A topic exists; pass --rotate to replace it.", file=sys.stderr)
        return 1
    topic = "md-" + secrets.token_urlsafe(18)
    stored = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            user,
            "-s",
            SERVICE,
            "-w",
            topic,
        ],
        capture_output=True,
        check=False,
    )
    sent = subprocess.run(
        ["gh", "secret", "set", SECRET, "-R", REPOSITORY],
        capture_output=True,
        check=False,
        input=topic.encode(),
    )
    if stored.returncode or sent.returncode:
        print("The keychain or gh refused the topic.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
