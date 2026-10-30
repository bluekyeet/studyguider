# PostgreSQL and uploads backup

These commands require Bash, Docker Compose, and the existing `pgvector/pgvector:pg17`
image. Run from the repository root on the Docker host; they do not work unchanged
in PowerShell. Set `SOURCE` to the **actual** Compose project name (see
`docker compose ls`) and use the same `.env`/environment as the running stack.
Compose needs both password variables even when only the database is used. Never
print the environment or run `docker compose config` in logs.

Backups contain private database records and uploads. Keep them outside the
repository, restrict access, encrypt them for storage and transfer, and follow
your retention policy. Do not include `.env` or credentials in the backup.

## Create a consistent backup

Stop all other writers as well as the API, including direct database clients and
processes writing to the uploads volume. The API remains stopped if any command
fails; restart it only after resolving the error. This causes downtime.

```bash
set -eu
SOURCE=studylarper                    # replace with the actual project name
BACKUP="$HOME/studyguider-backup-$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir "$BACKUP"                       # fails rather than overwrite a backup
docker compose -p "$SOURCE" stop api
docker compose -p "$SOURCE" exec -T db pg_dump -U studyguider -d studyguider -Fc > "$BACKUP/database.dump"
docker run --rm --network none --mount "type=volume,src=${SOURCE}_uploads,dst=/uploads,readonly" --mount "type=bind,src=$BACKUP,dst=/backup" pgvector/pgvector:pg17 tar -C /uploads -cf /backup/uploads.tar .
docker compose -p "$SOURCE" exec -T db pg_restore --list < "$BACKUP/database.dump" > /dev/null
tar -tf "$BACKUP/uploads.tar" > /dev/null
docker compose -p "$SOURCE" up -d api
printf 'Backup completed: %s\n' "$BACKUP"
```

The database must already be running and healthy. Verify the project and volume
names before starting: `docker compose -p "$SOURCE" ps` and
`docker volume inspect "${SOURCE}_uploads"`. The archive-list checks detect some
corruption, not every possible restore failure. Preserve the two files together.

## Restore into a new, isolated project

Use only a trusted backup: tar archives can contain dangerous paths or links.
Do not restore into the source project or existing volumes. Choose a fresh,
lowercase Compose project name and a private backup directory. The target uses
the current Compose configuration and credentials; the backup does not contain
the `.env` file. Ensure the current application/schema version is compatible.
These commands start only PostgreSQL, not the API, so they do not publish port
8000 or connect the restored application to external services.

```bash
set -eu
TARGET=studyguider-restore-test        # choose a unique, unused project name
BACKUP="$HOME/path-to-backup"          # absolute directory containing both files
test -s "$BACKUP/database.dump"
test -s "$BACKUP/uploads.tar"
test -z "$(docker compose -p "$TARGET" ps -aq)"
if docker volume inspect "${TARGET}_postgres_data" >/dev/null 2>&1 || docker volume inspect "${TARGET}_uploads" >/dev/null 2>&1; then
  printf 'Target volumes already exist; choose another project name.\n' >&2
  exit 1
fi
docker compose -p "$TARGET" up -d --wait db
docker compose -p "$TARGET" exec -T db pg_restore -U studyguider -d studyguider --exit-on-error --no-owner < "$BACKUP/database.dump"
docker volume create "${TARGET}_uploads" > /dev/null
docker run --rm --network none --mount "type=volume,src=${TARGET}_uploads,dst=/uploads" --mount "type=bind,src=$BACKUP,dst=/backup,readonly" pgvector/pgvector:pg17 tar -C /uploads -xf /backup/uploads.tar
docker compose -p "$TARGET" exec -T db psql -U studyguider -d studyguider -v ON_ERROR_STOP=1 -c 'SELECT current_database();'
docker run --rm --network none --mount "type=volume,src=${TARGET}_uploads,dst=/uploads,readonly" --mount "type=bind,src=$BACKUP,dst=/backup,readonly" pgvector/pgvector:pg17 tar -C /uploads -df /backup/uploads.tar
```

`pg_restore` exits on the first SQL error; a failed restore may leave a partial
target. Choose another fresh target rather than rerunning into it. The SQL check
confirms connectivity, and `tar -df` compares archived files with the restored
volume; neither proves application-level completeness. Check important records and
uploads before relying on the backup. To remove a disposable target after review,
first confirm `TARGET`, then run `docker compose -p "$TARGET" down` and explicitly
remove only its two volumes with `docker volume rm "${TARGET}_postgres_data" "${TARGET}_uploads"`.
