"""Run the servoom test suite.

Equivalent to ``python -m pytest tests``. The tests decode every bundled reference asset
and assert the output is byte-for-byte unchanged.

The manual "fetch/download" smoke flows that used to live here are now CLI commands:

    python -m servoom download <gallery_id>
    python -m servoom download-user <user_id>
    python -m servoom decode <path-or-folder>

(see ``python -m servoom --help``).
"""

import sys

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["tests", "-q", *sys.argv[1:]]))
