"""Machine-local measurement storage, kept outside the API/SCPI source checkout.

Set REDPITAYA_DATA_DIR to an absolute directory to override the default, for
example a VirtualBox shared host directory when running a notebook in Ubuntu.
This module resolves paths only; acquisition code creates its result folders.
"""

import os
from pathlib import Path
import re


def local_data_root():
    override = os.environ.get("REDPITAYA_DATA_DIR")
    if override:
        root = Path(os.path.expandvars(override)).expanduser()
        if not root.is_absolute():
            raise ValueError("REDPITAYA_DATA_DIR must be an absolute path outside the repository")
    elif os.name == "nt":
        root = Path.home() / "RedPitaya_local_data" / "RedPitaya_app"
    else:
        root = Path.home() / ".local" / "share" / "redpitaya" / "RedPitaya_app"
    root = root.resolve()
    repository = Path(__file__).resolve().parents[1]
    if root == repository or repository in root.parents:
        raise ValueError("Measurement storage must be outside the API/SCPI repository")
    return root


def results_directory(name):
    """Return a named test-results directory in machine-local storage."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
        raise ValueError("Results name must be a single directory name")
    return local_data_root() / "scpi-tests" / name
