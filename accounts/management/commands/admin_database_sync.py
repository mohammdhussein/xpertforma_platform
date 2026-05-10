from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import DatabaseError, connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone


DEFAULT_SYNC_APPS = ("accounts", "organizations", "training")


class Command(BaseCommand):
    help = "Synchronize app data additions and edits between local and Render databases."

    def add_arguments(self, parser):
        parser.add_argument(
            "--local",
            default="local",
            help="Database alias for the local database. Defaults to 'local'.",
        )
        parser.add_argument(
            "--remote",
            default="render",
            help="Database alias for the Render database. Defaults to 'render'.",
        )
        parser.add_argument(
            "--app",
            action="append",
            dest="app_labels",
            help=(
                "App label to sync. Can be passed multiple times. "
                "Defaults to accounts, organizations, and training."
            ),
        )
        parser.add_argument(
            "--conflict-winner",
            choices=("remote", "local"),
            default="remote",
            help=(
                "Which database wins when the same primary key was edited in both "
                "places. Defaults to remote."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write data. Without this flag the command only reports counts.",
        )
        parser.add_argument(
            "--skip-backup",
            action="store_true",
            help="Do not create JSON backups before applying changes.",
        )
        parser.add_argument(
            "--backup-dir",
            default=str(settings.BASE_DIR / "local_db_backups"),
            help="Directory for JSON backups. Defaults to local_db_backups.",
        )
        parser.add_argument(
            "--keep-transfer-files",
            action="store_true",
            help="Keep the temporary JSON transfer fixtures for inspection.",
        )

    def handle(self, *args, **options):
        local_alias = options["local"]
        remote_alias = options["remote"]
        app_labels = tuple(options["app_labels"] or DEFAULT_SYNC_APPS)

        self._validate_alias(local_alias)
        self._validate_alias(remote_alias)
        self._validate_distinct_databases(local_alias, remote_alias)
        self._validate_apps(app_labels)
        self._validate_matching_migrations(local_alias, remote_alias)

        self.stdout.write(self.style.MIGRATE_HEADING("Database sync plan"))
        self.stdout.write(f"Local alias:  {local_alias}")
        self.stdout.write(f"Render alias: {remote_alias}")
        self.stdout.write(f"Apps:         {', '.join(app_labels)}")
        self.stdout.write(f"Conflicts:    {options['conflict_winner']} wins")
        self.stdout.write("")

        for app_label in app_labels:
            self._write_counts(app_label, local_alias, remote_alias)

        if not options["apply"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Dry run only. Add --apply to copy additions and edits both ways."
                )
            )
            return

        started_at = perf_counter()
        backup_dir = Path(options["backup_dir"])
        backup_dir.mkdir(parents=True, exist_ok=True)

        if not options["skip_backup"]:
            timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
            local_backup = backup_dir / f"{timestamp}-{local_alias}-before-sync.json"
            remote_backup = backup_dir / f"{timestamp}-{remote_alias}-before-sync.json"
            self._dump_database(local_alias, app_labels, local_backup)
            self._dump_database(remote_alias, app_labels, remote_backup)
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"Backed up {local_alias}:  {local_backup}"))
            self.stdout.write(self.style.SUCCESS(f"Backed up {remote_alias}: {remote_backup}"))

        first_source, first_target = self._sync_order(
            local_alias=local_alias,
            remote_alias=remote_alias,
            conflict_winner=options["conflict_winner"],
        )
        self._copy_database(
            source_alias=first_source,
            target_alias=first_target,
            app_labels=app_labels,
            backup_dir=backup_dir,
            keep_transfer_files=options["keep_transfer_files"],
        )
        self._copy_database(
            source_alias=first_target,
            target_alias=first_source,
            app_labels=app_labels,
            backup_dir=backup_dir,
            keep_transfer_files=options["keep_transfer_files"],
        )

        elapsed = perf_counter() - started_at
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Database sync complete in {elapsed:.1f}s."))

    def _validate_alias(self, alias: str) -> None:
        if alias not in connections.databases:
            raise CommandError(
                f"Database alias '{alias}' is not configured. "
                "Set RENDER_DATABASE_URL for the Render database and, if needed, "
                "LOCAL_DATABASE_URL for the local database."
            )

    def _validate_distinct_databases(self, local_alias: str, remote_alias: str) -> None:
        if local_alias == remote_alias:
            raise CommandError("Local and Render database aliases must be different.")

        local_settings = self._identity_settings(local_alias)
        remote_settings = self._identity_settings(remote_alias)
        if local_settings == remote_settings:
            raise CommandError(
                "Local and Render aliases resolve to the same database. "
                "Check LOCAL_DATABASE_URL and RENDER_DATABASE_URL before syncing."
            )

    def _identity_settings(self, alias: str) -> tuple[str, str, str, str]:
        database = connections.databases[alias]
        return (
            database.get("ENGINE", ""),
            str(database.get("HOST", "")),
            str(database.get("PORT", "")),
            str(database.get("NAME", "")),
        )

    def _validate_apps(self, app_labels: tuple[str, ...]) -> None:
        for app_label in app_labels:
            try:
                django_apps.get_app_config(app_label)
            except LookupError as exc:
                raise CommandError(f"Unknown app label '{app_label}'.") from exc

    def _validate_matching_migrations(self, local_alias: str, remote_alias: str) -> None:
        known_migrations = self._known_migrations(local_alias)
        local_raw_migrations = self._applied_migrations(local_alias)
        remote_raw_migrations = self._applied_migrations(remote_alias)
        local_stale_migrations = local_raw_migrations - known_migrations
        remote_stale_migrations = remote_raw_migrations - known_migrations
        local_migrations = local_raw_migrations & known_migrations
        remote_migrations = remote_raw_migrations & known_migrations

        if local_stale_migrations:
            self.stdout.write(
                self.style.WARNING(
                    "Ignoring stale local migration history entries: "
                    f"{self._format_migrations(sorted(local_stale_migrations))}"
                )
            )
        if remote_stale_migrations:
            self.stdout.write(
                self.style.WARNING(
                    "Ignoring stale Render migration history entries: "
                    f"{self._format_migrations(sorted(remote_stale_migrations))}"
                )
            )

        if local_migrations == remote_migrations:
            return

        local_only = sorted(local_migrations - remote_migrations)
        remote_only = sorted(remote_migrations - local_migrations)
        details = []
        if local_only:
            details.append(f"local-only migrations: {self._format_migrations(local_only)}")
        if remote_only:
            details.append(f"remote-only migrations: {self._format_migrations(remote_only)}")
        raise CommandError(
            "Databases do not have the same applied migrations. Run migrations first; "
            + "; ".join(details)
        )

    def _known_migrations(self, alias: str) -> set[tuple[str, str]]:
        try:
            loader = MigrationLoader(connections[alias], ignore_no_migrations=True)
        except Exception as exc:  # pragma: no cover - keeps the command error readable.
            raise CommandError(f"Could not load migration files for '{alias}': {exc}") from exc
        return set(loader.disk_migrations)

    def _applied_migrations(self, alias: str) -> set[tuple[str, str]]:
        connection = connections[alias]
        try:
            return set(MigrationRecorder(connection).applied_migrations())
        except Exception as exc:  # pragma: no cover - keeps the command error readable.
            raise CommandError(f"Could not read migrations from '{alias}': {exc}") from exc

    def _format_migrations(self, migrations: list[tuple[str, str]]) -> str:
        return ", ".join(f"{app}.{name}" for app, name in migrations[:10])

    def _write_counts(self, app_label: str, local_alias: str, remote_alias: str) -> None:
        self.stdout.write(self.style.HTTP_INFO(app_label))
        for model in django_apps.get_app_config(app_label).get_models():
            local_count = self._count_model(model, local_alias)
            remote_count = self._count_model(model, remote_alias)
            self.stdout.write(
                f"  {model.__name__}: {local_alias}={local_count}, {remote_alias}={remote_count}"
            )

    def _count_model(self, model, alias: str) -> int:
        try:
            return model.objects.using(alias).count()
        except DatabaseError as exc:
            raise CommandError(
                f"Could not read {model._meta.label} from '{alias}'. "
                "Run migrations for that database before syncing."
            ) from exc

    def _sync_order(
        self,
        *,
        local_alias: str,
        remote_alias: str,
        conflict_winner: str,
    ) -> tuple[str, str]:
        if conflict_winner == "remote":
            return remote_alias, local_alias
        return local_alias, remote_alias

    def _dump_database(self, alias: str, app_labels: tuple[str, ...], output_path: Path) -> None:
        call_command(
            "dumpdata",
            *app_labels,
            database=alias,
            indent=2,
            output=str(output_path),
            verbosity=0,
        )

    def _copy_database(
        self,
        *,
        source_alias: str,
        target_alias: str,
        app_labels: tuple[str, ...],
        backup_dir: Path,
        keep_transfer_files: bool,
    ) -> None:
        transfer_path = self._new_transfer_path(source_alias, target_alias, backup_dir)
        self._dump_database(source_alias, app_labels, transfer_path)
        call_command("loaddata", str(transfer_path), database=target_alias, verbosity=0)

        self.stdout.write(
            self.style.SUCCESS(f"Copied additions and edits from {source_alias} to {target_alias}.")
        )

        if not keep_transfer_files:
            transfer_path.unlink(missing_ok=True)

    def _new_transfer_path(self, source_alias: str, target_alias: str, backup_dir: Path) -> Path:
        with NamedTemporaryFile(
            prefix=f"{source_alias}-to-{target_alias}-",
            suffix=".json",
            dir=backup_dir,
            delete=False,
        ) as temp_file:
            return Path(temp_file.name)
