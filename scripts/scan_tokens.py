"""Count each secret's whole value and fragments in the files under a folder.

The secrets come from environment variables named on the command line, so no
value is ever an argument or printed; only counts are.  Fragments follow
PLAN.md D50: each dot-separated part and each sixteen-character window.
Exits 1 when any count is above zero, 2 for a missing variable.
"""

import os
import pathlib
import sys

WINDOW = 16


def fragments(secret: str) -> list[str]:
    """Return the dot-separated parts and sixteen-character windows of a secret."""
    parts = [part for part in secret.split(".") if len(part) >= WINDOW // 2]
    windows = [secret[i : i + WINDOW] for i in range(max(len(secret) - WINDOW, 0) + 1)]
    return [*parts, *(w for w in windows if len(w) == WINDOW)]


def count(secret: str, text: str) -> tuple[int, int]:
    """Return how often the whole secret and any of its fragments occur in text."""
    return text.count(secret), sum(text.count(f) for f in fragments(secret))


def main(argv: list[str]) -> int:
    """Scan the folder in argv[0] for the secrets named by the variables after it."""
    folder, names = pathlib.Path(argv[0]), argv[1:]
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        print(f"not set: {', '.join(missing)}", file=sys.stderr)
        return 2
    files = [path for path in sorted(folder.rglob("*")) if path.is_file()]
    text = "\n".join(path.read_text(errors="replace") for path in files)
    found = 0
    for name in names:
        whole, parts = count(os.environ[name], text)
        print(f"{name}: whole {whole}, fragments {parts}, in {len(files)} files")
        found += whole + parts
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
