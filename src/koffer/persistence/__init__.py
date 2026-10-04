"""SQLite persistence: connection factory, migrations, FTS, backup."""

from koffer.persistence.backup import BackupError, BackupManifest, backup_database, restore_database
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.migrations import MigrationError, MigrationRunner, apply_migrations
from koffer.persistence.search_index import (
    SearchIndexService,
    path_terms_from_paths,
    sanitize_fts_query,
)

__all__ = [
    "BackupError",
    "BackupManifest",
    "ConnectionFactory",
    "MigrationError",
    "MigrationRunner",
    "SearchIndexService",
    "apply_migrations",
    "backup_database",
    "path_terms_from_paths",
    "restore_database",
    "sanitize_fts_query",
]
