# CLAUDE.md - BestYet build conventions

Read `bestyet-spec-v0.12.md` before writing anything. The spec is the source of truth for scope and data model; this file is the source of truth for how the code is written. Where they conflict, ask, do not guess.

## Project

- Name: BestYet. Repo slug: `bestyet`. Hosted on GitHub.
- Licence: AGPL-3.0-or-later. `LICENSE` at repo root. Dependencies must be permissively licensed (MIT/BSD/Apache-2.0/Unlicense); flag anything copyleft before adding it.
- Django 5.2 LTS (pin `Django>=5.2,<5.3`), Python 3.12+.
- Dependency and venv management: `uv` only. `pyproject.toml` is authoritative. No pip, no requirements.txt.
- Lint/format: ruff (`ruff check` and `ruff format`) must pass before any commit.

## Layout

```
bestyet/
  config/            # settings, urls, wsgi
  apps/
    accounts/        # profile, share_history, export
    exercises/       # Exercise, MuscleGroup, import command
    routines/        # Routine, RoutineExercise, progression rules
    logbook/         # WorkoutSession, SetLog, CardioLog, active workout UI
    metrics/         # BodyMetric
    analytics/       # PRs, e1RM, volume queries and charts, leaderboards, notices
  templates/         # base + per-app dirs; HTMX partials in templates/<app>/partials/
  static_src/        # tailwind input.css
  static/            # built assets (committed: no)
```

## Configuration

- Runtime config read from an INI file (`bestyet.ini`), path from env var `BESTYET_CONFIG`. Sections for django (secret key ref, hosts, debug), paths (db, media), and anything deploy-specific.
- No secrets in the repo, ever. Secret key and any credentials live in the INI on the host (host file perms 600) or env vars.
- `DEBUG=False` unless the INI explicitly says otherwise.

## Database

- SQLite with WAL. In `DATABASES["default"]["OPTIONS"]`:
  - `transaction_mode = "IMMEDIATE"`
  - `init_command` enabling WAL, `busy_timeout` (5000 ms), `synchronous=NORMAL`, `foreign_keys=ON`
- Migrations: never edit an applied migration. New migration per change. Review the generated SQL for anything touching existing data.
- Backups use `VACUUM INTO` or the sqlite3 `.backup` API. Never document or script a raw file copy of a hot WAL database.
- Portability: no SQLite-specific SQL anywhere except the configured connection pragmas. ORM only; `JSONField` for JSON. A Postgres move must remain a config change plus data migration.

## Hard invariants (violating any of these is a bug, not a style issue)

1. `WorkoutSession`, `SetLog`, `CardioLog` use client-generated UUIDv4 primary keys supplied by the frontend.
2. All write endpoints for those models are idempotent upserts keyed on the UUID. Submitting the same request twice produces one row.
3. User-generated rows soft-delete via `deleted_at`. Default managers exclude soft-deleted rows. Hard delete only through admin.
4. Every model with a `user` FK gets `updated_at` maintained automatically.
5. Every queryset in every view is scoped to `request.user`. The only cross-user reads are: shared-history views (gated on the target's `share_history=True`), leaderboard/notice aggregates (pseudonym-or-name plus metric only), and friendship pairs. No other exceptions, including exports.
6. Progression suggestions are display-only. Nothing ever writes a suggested weight into a target or a log.
7. `weight_kg` may be negative only when the exercise `load_type` is `bodyweight_plus`. Validate at the form and model level.
8. Export endpoints serve only `request.user`'s data and exclude soft-deleted rows.
9. Planned/scaffold sets are never persisted. A `SetLog` row exists only for a completed set. Sessions may contain exercises not in their routine (in-session swap/add is a feature, not an error state).
10. Progression and deload streaks are computed from history at read time, never stored, and only over sessions where the exercise was actually performed.
11. `bar_weight_kg` may be set only on `load_type=external` exercises. Plate calculator maths is per-side, greedy from the profile's `plate_inventory`, and purely display logic.
12. Curated routines are system rows: `owner` null, `visibility=curated`, read-only outside fixtures/admin, adopted only by cloning. Curated fixture names stay generic; no third-party program brand names.
13. Rotation "next up" is a suggestion. Nothing prevents starting any routine or a freeform session, and `session_rpe` is never required to finish a session.
14. Leaderboards are computed live across all users (no stored rank tables). Identity is pseudonymous by default: real display names appear only between accepted friends, on boards and in notices alike. Board entries never link into another user's sessions unless that user has `share_history=True`, friend or not. Missing `sex` or a bodyweight within 30 days excludes a user from DOTS/ratio boards with a hint, never an error.
15. Notices are the only stored derived data. Lead notices are created server-side at session finish only, idempotently per lead transition (edits and re-saves never duplicate), and cover absolute best-lift boards only in v1. Friendship notices are created at request/accept events. `exercise` and `value_kg` are null on friendship kinds.
16. Warm-up generator output is scaffold, subject to invariant 9. Backdated sessions get no special casing anywhere: streaks, boards, PRs and notices treat them purely by their dates, with `started_at` never in the future.
17. Any mutation of a finished session sets `edited_at` and triggers notice reconciliation: notices whose lead transition no longer holds are deleted, new transitions fire, and the whole operation stays idempotent.
18. Per-metric validation is enforced at form and model level: reps for `weight_reps`, duration for `weight_time`, distance for `weight_distance_time`; `side` required iff the exercise is unilateral. Non-rep sets are excluded from e1RM and tonnage; unilateral side rows count 0.5 each toward volume. Free-text notes (session and set) are never rendered in shared views or leaderboard contexts.
19. Any session whose date falls within any `DeloadPeriod` row (past or present, live or backdated) is excluded from progression and stall-streak evaluation. Deload week mode changes suggestions only; it never writes targets or logs.
20. `is_mobility` exercises are excluded from volume counting, freshness, and volume leaderboards. Rest analytics are derived from `completed_at` deltas at read time (block-internal, first set and >15 min gaps excluded); actual rest is never stored.
21. Unfinished sessions are never auto-discarded; recovery is banner + prompt only. Set-delete undo restores by clearing `deleted_at` through an idempotent endpoint. Tapping a set row never completes it; only the tick target does. The first-run wizard is skippable and never blocks access.
22. Friendships are mutual: pending until the addressee accepts, either side can remove, and acceptance reveals display names only, never history access. `sex` is used solely for DOTS coefficient selection. DOTS coefficients are vendored from OpenPowerlifting's published source; per-lift DOTS applies only to `dots_eligible` exercises.

## Frontend

- Server-rendered Django templates + HTMX. HTMX swaps target partials under `templates/<app>/partials/`; name partials `_<thing>.html`.
- JS: small vanilla modules in `static_src/js/` (rest timer, steppers, UUID generation via `crypto.randomUUID()`). No node, no npm, no React, no bundler.
- Tailwind via the standalone CLI binary. Content globs: `templates/**/*.html`. Build: `tailwindcss -i static_src/input.css -o static/css/app.css --minify`; dev uses `--watch`. Document the binary version in the README.
- No localStorage/sessionStorage for anything that matters; server state is truth. (v2 offline queue will use IndexedDB; do not pre-build it.)
- Charts: uPlot, data injected as JSON in a `<script type="application/json">` block.
- Mobile-first: design for a phone viewport, then let it stretch. Touch targets minimum 44px, including the set-completion tick. Bottom tab bar (Home, Workout, Boards, More) + badged notices bell in the top bar. Numeric fields use `inputmode=decimal` with select-on-focus. Extra-large type scale on the active workout screen. Wake lock module (`navigator.wakeLock`) acquired for active sessions, re-acquired on `visibilitychange`.

## Testing

- pytest + pytest-django. Tests live beside each app in `tests/`.
- Mandatory suites, non-negotiable:
  - Cross-user isolation: user A can never read or write user B's rows via any view, including exports, with and without `share_history`.
  - Idempotency: replaying set/session/cardio writes with the same UUID does not duplicate.
  - Progression engine: table-driven cases for double and linear rules, including RPE gates, warm-up/drop-set exclusion, AMRAP evaluation, and deload-week exclusion (a deload session never counts as a failed session).
  - e1RM/PR/volume queries against fixture data with hand-computed expected values, covering all three exercise metrics, unilateral 0.5 counting, and AMRAP evaluation.
  - Notice reconciliation: a post-finish edit that invalidates a lead deletes the stale notice without duplicating others.
  - DOTS scores validated against published calculator test vectors; identity tests prove non-friends see pseudonyms everywhere (boards and notices) and that friendship never grants history access.
- Import command tested against a small vendored sample of free-exercise-db JSON, not the live repo.

## Security posture (internet-facing)

- django-axes enabled with lockout and structured failure logging (fail2ban consumes this on the host).
- Secure + HttpOnly cookies, `SECURE_PROXY_SSL_HEADER` set for Caddy, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` pinned from the INI.
- Admin on a non-default path defined in the INI.
- Registration stays disabled. Do not add a signup view.

## Deployment artefacts to produce (kept in `deploy/`)

- systemd unit for gunicorn (uv venv path, `BESTYET_CONFIG` env, `Restart=on-failure`).
- Caddyfile: reverse proxy to gunicorn, `file_server` for `/media/*` with long cache headers, security headers, optional admin path IP restriction. Caddy owns TLS via automatic ACME; do not script any other certificate tooling.
- Backup script (`VACUUM INTO` + rsync hook point).

## Working style

- Follow the build order in the spec, section 10. Finish and test a step before starting the next.
- Small, focused commits with imperative messages. No CI workflows (decided): ruff and pytest are local gates and must pass before every commit.
- Do not add features not in the spec. If something seems missing or wrong, stop and ask.
- No Docker, no Postgres, no Celery, no node. If a problem appears to need one of these, it is being solved wrong; ask first.
