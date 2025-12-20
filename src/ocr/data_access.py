from __future__ import annotations

import hashlib
from pathlib import Path


class DataAccessError(Exception):
    pass


def resolve_under_data_root(*, data_root: Path, relpath: str) -> Path:
    """
    Resolve a relative path under an explicit, resolved data_root.

    Architectural requirements (docs/architecture/07_DATA_RULES_AND_ACCESS.MD):
    - This module must not assume where data lives.
    - This module must not read environment variables.
    - All data access is rooted at the resolved data_root passed in explicitly.
    """

    if relpath.startswith(("/", "\\")) or (":" in relpath and "\\" in relpath):
        # Absolute path / Windows drive patterns are not permitted as "relpath".
        raise DataAccessError(f"Expected a relative path under data_root, got: {relpath!r}")

    root = data_root.expanduser().resolve()
    candidate = (root / relpath).resolve()

    # Python 3.11 has Path.is_relative_to, but keep a robust fallback.
    try:
        ok = candidate.is_relative_to(root)
    except AttributeError:  # pragma: no cover
        root_str = str(root)
        cand_str = str(candidate)
        ok = cand_str == root_str or cand_str.startswith(root_str + "/")

    if not ok:
        raise DataAccessError(
            f"Path traversal or external reference detected: relpath={relpath!r}"
        )

    return candidate


def sha256_file(path: Path) -> str:
    """
    Compute SHA-256 of a file for audit metadata.

    Note: reading the file is allowed because access is still mediated via
    explicit data_root/path resolution by the caller.
    """

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

