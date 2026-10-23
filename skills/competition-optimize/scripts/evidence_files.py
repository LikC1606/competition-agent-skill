"""Read and verify candidate result and snapshot bytes within one operation.

File digests may be reused only in an explicit EvidenceReads view. Directories
are enumerated afresh; every use checks the current file identity. No archive,
measurement plan or learning module is imported.
"""

from __future__ import annotations

import pathlib
import time
from typing import Any

import implementation_reviews
from candidate_evidence import ArchiveFailure, canonical, implementation_identity, sha256


class EvidenceReads:
    """Reuse file digests within one evidence view, never across requests.

    Recheck file identity on every use. Directories are deliberately not cached:
    their inventories and each member's current identity must still be visited.
    Only digests are retained, not model/data/result bytes.
    """

    def __init__(self) -> None:
        self._files: dict[pathlib.Path, tuple[tuple[int, ...], str]] = {}
        # Same-size writes can share a filesystem timestamp tick. Recent files
        # are always reread; archived snapshots older than this view can reuse
        # digests after their full identity is checked again. No waiting.
        self._stable_before_ns = time.time_ns() - 1_000_000_000

    @staticmethod
    def _identity(path: pathlib.Path) -> tuple[int, ...]:
        info = path.stat()
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)

    def digest(self, path: pathlib.Path) -> str:
        path = path.expanduser().resolve(strict=True)
        identity = self._identity(path)
        previous = self._files.get(path)
        if (previous is not None and previous[0] == identity
                and max(identity[-2:]) < self._stable_before_ns):
            return previous[1]
        return self._read(path, identity)[1]

    def _read(self, path: pathlib.Path, identity: tuple[int, ...]) -> tuple[bytes, str]:
        raw = path.read_bytes()
        digest = sha256(raw)
        if self._identity(path) == identity:
            self._files[path] = (identity, digest)
        return raw, digest

    def read_bytes(self, path: pathlib.Path) -> bytes:
        """Read required contents and share their digest with later checks."""
        path = path.expanduser().resolve(strict=True)
        return self._read(path, self._identity(path))[0]


def hash_path(path: pathlib.Path, *, reads: EvidenceReads | None = None) -> str:
    """Hash a file or a deterministic directory listing."""
    path = path.expanduser().resolve(strict=True)
    if path.is_file():
        return reads.digest(path) if reads is not None else sha256(path.read_bytes())
    if not path.is_dir():
        raise ArchiveFailure("invalid_artifact", f"Artifact is neither a file nor directory: {path}")
    members: list[dict[str, str]] = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            relative = item.relative_to(path).as_posix()
            members.append({"path": relative, "sha256": reads.digest(item) if reads is not None else sha256(item.read_bytes())})
    return sha256(canonical({"kind": "directory", "members": members}))


def verify_result(entry: dict[str, Any], *, reads: EvidenceReads | None = None) -> None:
    result = entry["result"]
    if result.get("result_path"):
        path = pathlib.Path(result["result_path"])
        digest = reads.digest(path) if reads is not None else sha256(path.read_bytes())
        if digest != result["result_sha256"]:
            raise ArchiveFailure("result_changed", f"Result bytes changed for {entry['candidate_id']}")


def verify_artifacts(entry: dict[str, Any], *, reads: EvidenceReads | None = None) -> list[pathlib.Path]:
    roots = []
    for key, name in entry["artifact_paths"].items():
        path = pathlib.Path(name).resolve(strict=True)
        if hash_path(path, reads=reads) != entry["artifacts"][key]:
            raise ArchiveFailure("parent_artifact_changed", f"Archived artifact changed for {entry['candidate_id']}: {key}")
        roots.append(path)
    if "implementation_review" in entry:
        try:
            implementation_reviews.verify(entry["implementation_review"], entry, implementation_identity(entry),
                                          lambda path: hash_path(path, reads=reads))
        except implementation_reviews.ReviewFailure as exc:
            raise ArchiveFailure("invalid_implementation_review", str(exc)) from exc
    return roots
