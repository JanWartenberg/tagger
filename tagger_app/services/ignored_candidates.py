"""Remember explicit candidate assessments independently of the rebuildable index."""

from contextlib import closing
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from tagger_app.services.duplicate_detection import CandidateGroup, CandidateMember


def candidate_identity(detector_id: str, group: CandidateGroup) -> str:
    # Scan members already carry canonical paths. Keep GUI-side hashing free of I/O.
    evidence = sorted(
        (
            os.path.normcase(os.path.normpath(member.path)),
            member.timestamp,
            member.source_field,
        )
        for member in group.members
    )
    return sha256(json.dumps([detector_id, evidence]).encode()).hexdigest()


@dataclass(frozen=True)
class IgnoredCandidate:
    identity: str
    detector_id: str
    group: CandidateGroup


class IgnoredCandidateStore:
    """Short-lived SQLite connections; call this filesystem boundary off the UI thread."""

    def __init__(self, index_root: str | Path) -> None:
        self.path = Path(index_root) / ".tagger" / "ignored_candidates.sqlite"

    def list(self) -> tuple[IgnoredCandidate, ...]:
        if not self.path.exists():
            return ()
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            rows = connection.execute(
                "SELECT identity, detector, candidate FROM ignored_candidates ORDER BY rowid DESC"
            ).fetchall()
        return tuple(
            IgnoredCandidate(
                identity,
                detector,
                CandidateGroup(
                    data["group_id"],
                    tuple(
                        CandidateMember(
                            **{**member, "iptc_tags": tuple(member["iptc_tags"])}
                        )
                        for member in data["members"]
                    ),
                ),
            )
            for identity, detector, candidate in rows
            for data in [json.loads(candidate)]
        )

    def is_ignored(self, detector_id: str, group: CandidateGroup) -> bool:
        identity = candidate_identity(detector_id, group)
        return any(record.identity == identity for record in self.list())

    def remember(self, detector_id: str, group: CandidateGroup) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS ignored_candidates "
                "(identity TEXT PRIMARY KEY, detector TEXT NOT NULL, candidate TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR REPLACE INTO ignored_candidates VALUES (?, ?, ?)",
                (
                    candidate_identity(detector_id, group),
                    detector_id,
                    json.dumps(asdict(group)),
                ),
            )

    def restore(self, identity: str) -> None:
        if self.path.exists():
            with (
                closing(sqlite3.connect(self.path, timeout=5)) as connection,
                connection,
            ):
                connection.execute(
                    "DELETE FROM ignored_candidates WHERE identity = ?", (identity,)
                )

    def clear(self) -> None:
        if self.path.exists():
            with (
                closing(sqlite3.connect(self.path, timeout=5)) as connection,
                connection,
            ):
                connection.execute("DELETE FROM ignored_candidates")
