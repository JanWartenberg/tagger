import contextlib
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from migrate_index import _backup_database, main, migrate


class IndexMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / "old"
        self.new = self.root / "new"
        self.new.mkdir()
        self.db = self.new / ".tagger" / "index.sqlite"
        self.db.parent.mkdir()
        with contextlib.closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript("""
                CREATE TABLE photos(path TEXT PRIMARY KEY);
                CREATE TABLE tags(id INTEGER PRIMARY KEY, tag TEXT);
                CREATE TABLE photo_tags(
                    photo_path TEXT REFERENCES photos(path),
                    tag_id INTEGER REFERENCES tags(id)
                );
                INSERT INTO tags VALUES (1, 'Möwe');
            """)
            conn.execute("INSERT INTO photos VALUES (?)", (str(self.old / "a.jpg"),))
            conn.execute(
                "INSERT INTO photo_tags VALUES (?, 1)", (str(self.old / "a.jpg"),)
            )

    def photo_path(self, database):
        with contextlib.closing(sqlite3.connect(database)) as conn:
            return conn.execute("SELECT path FROM photos").fetchone()[0]

    def test_legacy_schema_preserves_tags_and_relationships(self):
        self.assertEqual(
            migrate(self.old, self.new, database=self.db, dry_run=True), (1, 1)
        )
        self.assertEqual(self.photo_path(self.db), str(self.old / "a.jpg"))
        self.assertEqual(list(self.db.parent.glob("*.before-migration-*")), [])
        self.assertEqual(migrate(self.old, self.new, database=self.db), (1, 1))
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                conn.execute(
                    "SELECT photo_path, tag FROM photo_tags JOIN tags ON tag_id = id"
                ).fetchall(),
                [(str(self.new / "a.jpg"), "Möwe")],
            )

    def test_refresh_tables_are_cleared_when_present(self):
        with contextlib.closing(sqlite3.connect(self.db)) as conn, conn:
            for table in ("refresh_paths", "refresh_directories", "refresh_checkpoint"):
                conn.execute(f"CREATE TABLE {table}(value TEXT)")
                conn.execute(f"INSERT INTO {table} VALUES ('stale')")
        migrate(self.old, self.new, database=self.db)
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            for table in ("refresh_paths", "refresh_directories", "refresh_checkpoint"):
                self.assertEqual(conn.execute(f"SELECT * FROM {table}").fetchall(), [])

    def test_repeated_migration_in_same_second_keeps_original_backup(self):
        with patch("migrate_index.datetime") as clock:
            clock.now.return_value.strftime.return_value = "same-second"
            migrate(self.old, self.new, database=self.db)
            first_backup = next(self.db.parent.glob("*.before-migration-*"))
            migrate(self.old, self.new, database=self.db)
        self.assertEqual(len(list(self.db.parent.glob("*.before-migration-*"))), 2)
        self.assertEqual(self.photo_path(first_backup), str(self.old / "a.jpg"))

    def test_backup_refuses_to_overwrite_existing_file(self):
        backup = self.root / "existing.sqlite"
        backup.write_bytes(b"keep me")
        with self.assertRaises(FileExistsError):
            _backup_database(self.db, backup)
        self.assertEqual(backup.read_bytes(), b"keep me")

    def run_cli(self, source):
        output = io.StringIO()
        with (
            patch(
                "sys.argv",
                [
                    "migrate_index.py",
                    str(self.old),
                    str(self.new),
                    "--database",
                    str(source),
                ],
            ),
            contextlib.redirect_stdout(output),
        ):
            main()
        return output.getvalue()

    def test_in_place_message_reports_backup(self):
        self.assertIn("A .before-migration backup was created", self.run_cli(self.db))
        self.assertEqual(len(list(self.db.parent.glob("*.before-migration-*"))), 1)

    def test_copy_message_reports_preserved_source(self):
        source = self.root / "source.sqlite"
        self.db.rename(source)
        output = self.run_cli(source)
        self.assertIn(f"Source database preserved at: {source}", output)
        self.assertNotIn("backup was created", output)
        self.assertEqual(self.photo_path(source), str(self.old / "a.jpg"))
        self.assertEqual(self.photo_path(self.db), str(self.new / "a.jpg"))


if __name__ == "__main__":
    unittest.main()
