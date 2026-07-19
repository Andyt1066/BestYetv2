# BestYet

Self-hosted, internet-facing, mobile-first web app for logging gym sessions,
cardio, and body metrics. Django 5.2 + HTMX + SQLite (WAL), served by gunicorn
behind Caddy. Licensed AGPL-3.0-or-later.

The spec (`bestyet-spec-v0.12.md`) is the source of truth for scope and data
model; `CLAUDE.md` for code conventions.

## Development setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync

# Local config: copy the example, fill in a secret key, set debug = true
cp bestyet.example.ini bestyet.ini
chmod 600 bestyet.ini
export BESTYET_CONFIG="$PWD/bestyet.ini"

uv run python manage.py migrate
uv run python manage.py createsuperuser   # registration is disabled by design
uv run python manage.py runserver
```

## Tailwind CSS

Built with the **standalone Tailwind CLI v4.3.3** (no node). Download the
binary for your platform from
<https://github.com/tailwindlabs/tailwindcss/releases> into `tools/tailwindcss`
(gitignored) and make it executable.

```sh
# one-off build
tools/tailwindcss -i static_src/input.css -o static/css/app.css --minify

# during development
tools/tailwindcss -i static_src/input.css -o static/css/app.css --watch
```

## Vendored frontend libraries

`static_src/js/vendor/` carries htmx 2.0.7 (BSD-2-Clause) and SortableJS
1.15.6 (MIT). No node toolchain; update by replacing the files.

## Seeding the exercise library

```sh
git clone --depth 1 https://github.com/yuhonas/free-exercise-db /tmp/fed
uv run python manage.py import_exercises /tmp/fed/dist/exercises.json --images-dir /tmp/fed/exercises
uv run python manage.py loaddata curated_routines   # after activating its exercises
```

The import is idempotent and never overwrites curation flags (`active`,
`load_type`, `bar_weight_kg`, ...) on re-run.

## Quality gates

Both must pass before every commit; there is deliberately no CI.

```sh
uv run ruff check && uv run ruff format --check
uv run pytest
```

## Deployment

See `deploy/` (systemd unit, Caddyfile, backup script) once produced. Backups
must use `VACUUM INTO` or the sqlite3 `.backup` API — never a raw file copy of
a hot WAL database.
