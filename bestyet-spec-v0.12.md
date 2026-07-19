# BestYet - Architecture & Data Model Spec v0.12

Status: final, post-audit. Nine consistency defects found in a full read-through and corrected in this version; no scope change.

## 1. Summary

**BestYet**: self-hosted, internet-facing, mobile-first web app (installable PWA) for logging gym sessions, cardio, and body metrics. Repo slug `bestyet` on GitHub (private for now), licensed **AGPL-3.0-or-later**. Two users initially (Andy, Robyn), proper multi-user auth from day one, with acknowledged ambition to become a real product later. Routines are user-created from a standardised exercise library, shareable between users, and supplemented by a curated library of generically named starter routines; a good freeform session can be saved back as a routine. Users order routines into a rotation and the dashboard suggests what's next. The set model covers weight x reps, timed holds, and weighted carries, with unilateral left/right logging per exercise, AMRAP target sets, RPE on a fixed 6-10 scale, and mobility work carried by the time metric but excluded from volume. Sessions start from a routine as a planned-set scaffold (optional auto warm-up ramp, ghost text and a history sheet, live PR flashes), allow free mid-workout swaps (picker pre-filtered to the same primary muscle) and extras, respect configurable intra-superset rest, close with an optional session RPE, can be backdated, and stay editable afterwards with a visible edited marker. The app suggests progression (double progression by default), deloads after repeated stalls, and offers a one-tap deload week mode, but never auto-applies any of it. Weekly volume tracks against per-muscle-group targets with progress bars, alongside a muscle freshness grid and actual-vs-prescribed rest analytics. Barbell lifts get a plate calculator with per-exercise bar weight. A dedicated leaderboards section ranks best lifts in three families (absolute e1RM, bodyweight ratio, and DOTS for S/B/D plus a DOTS total board), alongside weekly volume, consistency, and cardio distance, across all users on the instance. Identity on boards and notices is pseudonymous by default, with real names revealed only between mutually accepted friends. An in-app notices feed carries best-lift lead changes and friend requests. Free-text notes never appear in shared views. Theme follows the system setting. Per-user CSV/JSON export included in v1; import is explicitly out of scope. The interaction layer: a four-tab bottom nav (Home, Workout, Boards, More) with a badged notices bell, dedicated tick targets for set completion, steppers plus tap-to-type entry, screen wake lock and extra-large numerals during active sessions, undo toasts backed by soft delete, dangling-session recovery, a favourites-first exercise picker, and a skippable guided first-run.

## 2. Stack

| Layer | Choice | Rationale |
|---|---|---|
| Framework | Django 5.2 LTS | Auth, sessions, permissions, admin built in. LTS supported to Apr 2028. |
| Python tooling | uv, pyproject.toml | Existing toolchain convention. |
| DB | SQLite, WAL mode | Set via Django `OPTIONS` (`init_command` for WAL/busy_timeout, `transaction_mode=IMMEDIATE`). Single node, low write volume: no reason for Postgres. |
| Frontend | Django templates + HTMX + focused vanilla JS modules | Logging UI is forms plus partial updates; the active workout screen carries a deliberate JS island (timer, wake lock, steppers, sheets, plate calc). One deploy unit. |
| CSS | Tailwind CSS via standalone CLI | Confirmed. Dense custom app UI (steppers, timers, superset grouping) is Tailwind territory; standalone binary keeps node out of the toolchain; purge keeps shipped CSS small. |
| Static files | WhiteNoise for app static; Caddy `file_server` for `/media/*` (exercise images) | Long cache headers on images. |
| Serving | gunicorn + systemd on a VM/LXC, behind Caddy | Confirmed. Caddy provides automatic ACME TLS; certman not used. |
| PWA | manifest.json + minimal service worker (app-shell cache only in v1) | Installable to home screen. |
| VCS | GitHub | Personal project at home; fits the AGPL open-source stance. |

### 2.1 Sync-readiness invariants (v1, non-negotiable)

Offline logging is deferred to v2, but v1 must not block it:

- Client-generated UUIDv4 primary keys on `WorkoutSession`, `SetLog`, `CardioLog`.
- Write endpoints are idempotent upserts keyed on that UUID (retrying a POST is safe).
- `updated_at` on every mutable row.
- Soft delete (`deleted_at`) on user-generated rows; hard delete only via admin.

With these in place, v2 offline is a service worker plus IndexedDB replay queue with no schema change. Single writer per user means no conflict resolution is needed (last-write-wins per row is correct by construction).

### 2.2 Product ambition: portability and licence

Confirmed: BestYet could become a real product. v1 stays single-instance and deliberately un-over-engineered, but three rules keep the door open:

- **DB portability**: no SQLite-specific SQL outside the configured connection pragmas. ORM queries only, `JSONField` for JSON, so a later SQLite-to-Postgres move is configuration plus a data migration, not a rewrite.
- **No tenancy foreclosure**: nothing user-facing is a global singleton; all settings that could differ per user live on the profile.
- **Licence**: AGPL-3.0-or-later, LICENSE at repo root. Coherent with a hosted product (AGPL obliges offering source to users of the hosted service; wger uses the same model). All dependencies are permissive (Django BSD, Tailwind and uPlot MIT, free-exercise-db Unlicense) and compatible; any future copyleft dependency gets flagged before adoption. One recorded caveat, noted not as legal advice: accepting outside contributions without a CLA makes any later relicensing (e.g. open core) effectively impractical. Decide on a CLA before accepting external PRs.
- **Repo visibility** (confirmed): private on GitHub indefinitely, publication decided later. No conflict with AGPL: its obligations trigger only on distribution or offering the service to third parties, so they lie dormant for a private household instance.
- **CI** (confirmed): none. No GitHub Actions workflows. Quality gates (ruff, pytest) run locally and must pass before commit, per CLAUDE.md.

**Roadmap boundary**: nutrition tracking (calories/protein) is a possible future module, explicitly out of v1 and v2; nothing in v1 needs to accommodate it beyond not colliding on names.

## 3. Auth, users, hardening

- Django built-in auth. Registration disabled; users created via admin.
- Per-user profile:
  - display name
  - preferred units (kg default; kg stored canonically regardless)
  - bodyweight goal (optional)
  - `share_history` (bool, default false): opt-in toggle making the user's sessions visible read-only to other users.
  - `plate_inventory` (JSON list of per-side plate sizes in kg, default `[25, 20, 15, 10, 5, 2.5, 1.25]`): feeds the plate calculator.
  - `deload_after_failures` (int, default 3) and `deload_percent` (decimal, default 10): stall-deload suggestion parameters.
  - `deload_week_percent` (decimal, default 50): deload week intensity. Deload windows themselves are `DeloadPeriod` rows (5.1), not a profile field, so historical windows remain evaluable.
  - `bodyweight_unit` enum: `kg` (default) / `st_lb` / `lb`. Display-only conversion for bodyweight and body metrics; storage is always kg, and lift weights display in kg regardless.
  - `sex` enum (male/female, nullable): used solely for DOTS coefficient selection. Null simply excludes the user from DOTS boards with a hint; never an error.
  - `pseudonym` (string, unique): auto-generated stable handle shown on boards and notices to non-friends; user-regenerable. Stable pseudonyms are linkable over time; accepted trade-off in exchange for followable competition.
- All user data is row-scoped by `user` FK. The only cross-user reads are: shared-history views (gated on `share_history`), leaderboard and notice aggregates (which expose pseudonym-or-name plus metric only), and friendship pairs. Cross-user leakage beyond those three is a test case, not a hope.

Internet-facing hardening (public exposure, no 2FA in v1):

- TLS, HSTS and security headers handled in the Caddyfile (Caddy issues and renews certificates automatically).
- Login throttling: django-axes (attempt lockout with logging).
- fail2ban filter on django-axes failure log lines, consistent with existing server patterns.
- `SECURE_PROXY_SSL_HEADER`, Secure + HttpOnly session/CSRF cookies, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` pinned to the public hostname.
- Admin mounted on a non-default path; optionally IP-restricted in the Caddyfile.
- 2FA (django-otp) noted as a v2 add if wanted; nothing in v1 blocks it.

## 4. Exercise library

Seed from **free-exercise-db** (github.com/yuhonas/free-exercise-db): 800+ exercises, JSON, Unlicense (public domain, no attribution obligations). Schema per record includes force, mechanic (compound/isolation), equipment, primaryMuscles, secondaryMuscles, instructions, images.

- Management command `import_exercises` ingests the dataset, `source=seed`, and copies **all** exercise images into the media directory. Measure total size at import; serve via Caddy with long-lived cache headers.
- Custom exercises added via Django admin (simple form later), `source=custom`.
- `active` flag, default false for seed rows; a curation pass marks the movements actually used so the picker isn't 800 entries deep. Search covers inactive rows so anything can be activated on demand.
- Muscle strings from the dataset map to a canonical `MuscleGroup` table (needed for volume analytics).

## 5. Data model

All tables get `created_at` / `updated_at`. User-generated tables additionally get `deleted_at`.

### 5.1 Reference

**MuscleGroup**
- `id`, `name` (chest, back, quads, hamstrings, glutes, shoulders, biceps, triceps, core, calves, forearms, ...)

**Exercise**
- `id` UUID
- `name`, `slug` (unique)
- `force` (push/pull/static, nullable), `mechanic` (compound/isolation, nullable), `equipment`
- `load_type` enum: `external` (logged weight is the load) / `bodyweight_plus` (logged weight is added load; negative values allowed for assisted variants, e.g. band-assisted pull-ups)
- `bar_weight_kg` (decimal, nullable): set only for barbell lifts (typically 20; fixed bars/EZ bars as appropriate). Non-null enables the plate calculator for that exercise; only valid with `load_type=external`.
- `metric` enum: `weight_reps` (default) / `weight_time` (planks, dead hangs) / `weight_distance_time` (carries). Drives which set fields are required.
- `unilateral` (bool, default false): when true, every set logs a side (left/right).
- `is_mobility` (bool, default false): stretching/mobility work, normally paired with `weight_time`. Logged like anything else but excluded from volume counting, the freshness grid, and volume leaderboards.
- `dots_eligible` (bool, default false): curation marks the squat, bench press, and deadlift (and close competition variants at curator discretion). Gates the DOTS boards.
- `instructions` (text), `image_paths` (JSON, nullable)
- `source` (seed/custom), `active` (bool), `created_by` (FK user, nullable)

**ExerciseMuscle** (through)
- `exercise` FK, `muscle_group` FK, `role` (primary/secondary)

**VolumeTarget**
- `user` FK, `muscle_group` FK, `sets_low` (int), `sets_high` (int)
- Unique on (user, muscle_group). Optional per group; drives the weekly volume progress bars.

**DeloadPeriod**
- `user` FK, `start_date`, `end_date`
- One row per deload week. "Start deload week" creates a row (today, today + 7); cancelling truncates `end_date` to today. Active = today falls within a row. Kept as rows rather than a single profile date so that progression evaluation can exclude sessions falling inside *any* historical window, including backdated ones.

**FavouriteExercise**
- `user` FK, `exercise` FK, unique together. Starred exercises surface first in the picker.

**Friendship**
- `requester` FK user, `addressee` FK user, `status` enum (pending/accepted), `created_at`, `responded_at` (nullable)
- Uniqueness enforced on the unordered pair. Mutual by construction: pending until the addressee accepts; either side can remove at any time.
- An accepted friendship reveals real display names to each other on boards and in notices. It grants nothing else; `share_history` remains a wholly separate consent.
- Requests are made by exact account username (pseudonyms are not searchable). Friend requests and acceptances arrive as notices.

### 5.2 Routines

**Routine**
- `id` UUID, `owner` FK user (nullable: null = curated system routine)
- `name`, `description`
- `visibility` (private/shared/curated): `curated` routines are system-provided, read-only, owner null, shipped as a fixture of generically named starters ("Beginner full-body 5x5", "Push/Pull/Legs 6-day", "Upper/Lower 4-day"). No branded program names (StrongLifts, 5/3/1 etc. are other parties' marks). Adoption is the same clone mechanism as shared routines.
- `cloned_from` (FK Routine, nullable): adopting a shared or curated routine clones it; edits never propagate between copies
- `archived` (bool)

**RoutineRotation**
- `user` FK, `position` (int), `routine` FK
- One ordered rotation list per user in v1. "Next up" = the routine following the most recent completed session's routine in rotation order (wrapping); if the last session was freeform or off-rotation, next up is unchanged. Archived routines cannot be added to the rotation and are skipped by next-up if archived while in it. Pure suggestion: the dashboard always allows picking any routine or freeform.

**RoutineExercise**
- `routine` FK, `exercise` FK
- `position` (int, ordering)
- `superset_group` (int, nullable): same non-null value = performed as a superset
- `target_sets` (int), `target_reps_low` / `target_reps_high` (int, high nullable for fixed reps)
- `target_rpe` (decimal, nullable)
- `rest_seconds` (int, nullable): drives the rest timer, firing after a full superset round for grouped exercises
- `superset_rest_seconds` (int, nullable): rest between partner exercises within a superset round; null = move straight to the partner
- `last_set_amrap` (bool, default false): final set is "as many reps as possible"; scaffold shows "max" instead of a rep target
- `target_duration_seconds` (int, nullable) and `target_distance_m` (decimal, nullable): targets for `weight_time` / `weight_distance_time` exercises, replacing rep targets
- `progression_style` enum: `none` / `double` (default) / `linear`
- `progression_increment_kg` (decimal, default 2.5)
- `notes`

### 5.3 Progression suggestions

Computed at session start for each RoutineExercise, displayed as a suggestion, never auto-applied. Rules (stated conventions, tunable):

- **double** (default): if, in the most recent session of this routine, every working set of this exercise hit `target_reps_high` (and `rpe <= target_rpe` where both are set), suggest `last weight + increment` and aim back at `target_reps_low`. Otherwise suggest same weight, more reps.
- **linear**: if all working sets were completed at target reps last session, suggest `last weight + increment` every session.
- **none**: prefill last session's numbers only.

Warm-up and drop sets are excluded from the evaluation.

**Deload** (suggestion-only, like everything else here): failure streaks are computed, not stored. A "failed session" is one where the exercise was performed at the same weight and the progression condition was not met. After `deload_after_failures` consecutive failures (profile setting, default 3), suggest `weight x (1 - deload_percent/100)` rounded to the nearest `progression_increment_kg`, displayed as a deload with the stall count. Sessions where the exercise was swapped out or not performed do not count toward the streak either way; evaluation only considers sessions containing working sets of that exercise.

**Deload week mode** (confirmed): a one-tap "start deload week" action creates a `DeloadPeriod` (today, today + 7). While a period is active: a banner shows the mode and remaining days (cancellable any time, which truncates the period), and every weight suggestion becomes `last working weight x deload_week_percent / 100` rounded to a loadable weight. Critical rule: any session whose date falls within *any* DeloadPeriod, past or present, backdated or live, is excluded from progression and stall-streak evaluation entirely, so a deload week can never register as failed sessions or trigger a stall deload. After a period ends, suggestions resume from the last session outside a deload window.

**Plate calculator**: for exercises with `bar_weight_kg` set, any target or logged weight can expand to a per-side plate breakdown: greedy largest-first from the user's `plate_inventory`, `(weight - bar) / 2` per side. If the weight is not achievable with the inventory, show the nearest achievable weights either side. Pure display logic, client-side.

**Warm-up ramp generator** (confirmed): per exercise block, a "generate warm-ups" action builds scaffold-only warm-up sets from the first working weight: empty bar x 10 (barbell exercises only), then approximately 40% x 8, 60% x 5, 80% x 3, each rounded to a loadable weight (plate inventory when `bar_weight_kg` is set, otherwise `progression_increment_kg`), skipping steps at or below the bar weight or duplicating a previous step. Percentages and reps are code constants in v1, stated as conventions. Generated sets follow the standard scaffold rule: `set_type=warmup`, persisted only when ticked.

**Metric scope**: the progression engine and warm-up generator apply to `weight_reps` exercises only. AMRAP sets are evaluated against `target_reps_high` like any other set (hitting it counts toward the double-progression condition; the actual rep count is displayed in history). `weight_time` and `weight_distance_time` exercises get prefill-only in v1: last performance shown, no automatic suggestions.

### 5.4 Logging

**WorkoutSession**
- `id` UUID (client-generated)
- `user` FK, `routine` FK (nullable: freeform sessions allowed)
- `started_at`, `ended_at` (nullable until finished)
- `edited_at` (nullable): set whenever the session or its sets are mutated after `ended_at` was set; drives a visible "edited" marker in every view of the session
- `session_rpe` (decimal 3,1, nullable): optional overall "how hard was that" rating captured at finish; never required to finish a session
- `notes`

**SetLog**
- `id` UUID (client-generated)
- `session` FK, `exercise` FK
- `position` (int, order within session)
- `set_type` enum: `normal` / `warmup` / `dropset`
- `superset_group` (int, nullable)
- `weight_kg` (decimal 6,2; negative permitted only for `bodyweight_plus` exercises), `reps` (int, nullable)
- `duration_seconds` (int, nullable), `distance_m` (decimal, nullable)
- `side` enum (left/right, nullable)
- Per-metric validation: `weight_reps` requires reps; `weight_time` requires duration; `weight_distance_time` requires distance (duration optional). `side` is required if and only if the exercise is unilateral.
- `rpe` (decimal 3,1, nullable)
- `notes`, `completed_at`

Drop sets are ordinary sequential rows with `set_type=dropset`; no parent-set FK.

**Active workout semantics** (confirmed): starting from a routine renders a planned-set scaffold (targets + progression suggestion) in the UI only. A `SetLog` row is created when a set is completed (ticked), never before, so unfinished planned sets leave no rows behind. Extra sets can be added freely beyond the plan. Exercises can be swapped or added mid-session without touching the routine: swapping replaces the remaining scaffold for that block, and logged sets always reference the exercise actually performed. `SetLog.exercise` is independent of the routine by design, so a session may legitimately contain exercises not in its routine.

**Backdated entry** (confirmed): a "log past session" flow reuses the active workout screen with a date/time picker for `started_at`/`ended_at` and the rest timer disabled. Validation: `started_at` not in the future, `ended_at >= started_at`. Backdated sessions flow into streaks, weekly boards, PRs and notices exactly as dated; no special casing.

**Post-finish editing** (confirmed): finished sessions stay fully editable. Any mutation sets `edited_at` (visible marker) and triggers notice reconciliation: leaders for affected exercises are recomputed, notices recording transitions that no longer hold are deleted, and any new transitions fire, all idempotently. Correcting a 1000kg typo therefore also retracts the false lead notice it generated.

**Save as routine** (confirmed): any session offers "save as routine": creates a private Routine from the session's working sets, exercises in order of first appearance, `target_sets` = working-set count, rep targets from min/max working reps (or duration/distance targets for non-rep metrics), superset groups carried over, progression defaults applied, warm-ups and drop sets excluded.

**CardioLog**
- `id` UUID (client-generated)
- `user` FK, `session` FK (nullable: cardio can attach to a gym session or stand alone)
- `activity` enum (treadmill, bike, rower, stairmaster, outdoor run, walk, swim, other)
- `duration_seconds` (int), `distance_m` (decimal, nullable)
- `performed_at`, `notes`

**BodyMetric**
- `user` FK, `recorded_on` (date)
- `metric` enum (weight_kg, waist_cm, chest_cm, hips_cm, arm_cm, thigh_cm, bodyfat_pct)
- `value` (decimal)
- Unique on (user, recorded_on, metric)

Row-per-metric rather than a wide table: adding a measurement type is an enum value, not a migration.

### 5.5 Derived data (not stored in v1)

PRs and e1RM are computed, not materialised. Indexes: `SetLog(exercise, session)`, `WorkoutSession(user, started_at)`, `BodyMetric(user, metric, recorded_on)`. At two users' data volume SQLite handles these live; add a PR cache table only if measured to be slow.

Conventions (stated, not universal truths):

- **e1RM**: Epley formula, `weight x (1 + reps/30)`. Warm-up sets excluded; sets over 12 reps excluded (all e1RM formulas are estimates and degrade at high reps).
- **bodyweight_plus exercises** (log added kg only): PRs and e1RM are computed on the added load and charts are labelled "+kg". Self-consistent over time but understates true load; a total-load estimate using the nearest logged bodyweight is a possible later enhancement, not v1.
- **PR types**: for `weight_reps`: max weight, best e1RM, max reps at a given weight. For `weight_time`: longest duration, with heaviest weighted duration secondary. For `weight_distance_time`: heaviest carry (max weight with distance logged) and longest distance. Non-rep sets are excluded from e1RM and tonnage entirely.
- **Live PR flash**: on each ticked set, the write response includes a PR check against these definitions and badges the row instantly. Display-only; stored PR state does not exist (5.5 stands).
- **Weekly volume**: hard sets (`normal` + `dropset`) per muscle group per ISO week; time/distance sets still count as hard sets, `is_mobility` exercises never do. Unilateral side rows count 0.5 each, so a left+right pair equals one set. Primary muscle counts 1.0, secondary 0.5 (factor is a setting). Tonnage (rep sets only) shown as a secondary figure. Where a `VolumeTarget` exists, current-week sets render as a progress bar against the low-high range.
- **RPE scale**: recorded and displayed as RPE 6.0-10.0 in 0.5 steps. No RIR display mode (confirmed).
- **Muscle freshness**: per muscle group, days since the most recent hard set with that group as primary. Mobility sets excluded. Computed live.
- **Rest analytics**: actual rest = `completed_at` delta between consecutive sets of the same exercise block within a session, excluding each block's first set and any delta over 15 minutes (treated as a break). Shown as actual vs prescribed `rest_seconds` per exercise. Derived only; no stored rest values.

### 5.6 Notices

The one deliberately stored derived artefact, because lead changes are point-in-time events:

**Notice**
- `id` UUID (server-generated), `user` FK (recipient)
- `kind` enum: `lead_taken` (recipient took a lead) / `lead_lost` (recipient's lead was taken) / `friend_request` / `friend_accepted`; extensible
- `exercise` FK (nullable), `actor` FK user (the other party), `value_kg` (decimal, nullable): exercise and value are set for lead kinds, null for friendship kinds
- `created_at`, `read_at` (nullable)

Lead notices are generated server-side at session finish only (never per set): recompute best-lift leaders for the exercises in the finished session, diff against pre-session leaders, and create paired notices for each transition. Friendship notices are generated at request and acceptance events. Lead-notice creation is idempotent per lead transition: re-saving or editing a session must not duplicate notices for a transition already recorded. Post-finish edits additionally reconcile: notices whose transition no longer holds after the edit are deleted. v1 lead-notice scope is absolute best-lift boards only; weekly boards (volume, consistency, cardio) change every session and would be noise.

## 6. Export (v1, per user)

Available from the profile/settings screen; a user can export **only their own data**.

- **CSV**: one file per dataset: sessions with sets flattened (session fields repeated per set row), cardio, body metrics.
- **JSON**: single structured dump (profile, routines owned, rotation, volume targets, favourites, sessions with nested sets, cardio, body metrics). Friendships and notices are excluded: the former are bilateral records, the latter ephemeral. Import is explicitly out of scope (confirmed): restore is handled by database backups, not application-level re-ingestion.
- Streamed responses; excludes soft-deleted rows; timestamps in ISO 8601.

## 7. Leaderboards (dedicated section)

Instance-wide competitive boards, computed live like everything else in 5.5. No stored rank tables: **every user on the instance is always included** (confirmed), but identity is **pseudonymous by default**. Real display names appear only between mutually accepted friends (section 5.1 Friendship); everyone else sees stable pseudonyms. This replaces the earlier "opt-in participation flag before non-household deployment" prerequisite: metric participation stays universal, identity exposure is opt-in via friendship. Recorded honestly: at two users, pseudonymity is cosmetic (elimination deanonymises), and its real function begins at roughly five-plus users.

Boards (tabs on one screen), each with timeframe selectors where sensible (this week / 30 days / all-time):

1. **Best lifts**, in three families:
   - **Absolute**: per exercise, best e1RM ranked. Existing conventions apply: warm-ups excluded, sets over 12 reps excluded. `bodyweight_plus` exercises rank on added load, labelled "+kg". Overview lists exercises with their current leader.
   - **Ratio**: best e1RM ÷ bodyweight for `external`-load exercises. `bodyweight_plus` exercises are excluded from ratio boards in v1.
   - **DOTS**: for `dots_eligible` lifts only, best e1RM x DOTS coefficient (500 divided by a fourth-degree polynomial in bodyweight with sex-specific coefficients). Plus a **DOTS total** board: sum of a user's best e1RM across the three eligible lifts within the timeframe, x coefficient; all three lifts required to appear, and the coefficient uses the bodyweight nearest the most recent of the three qualifying sets (still subject to the 30-day rule). Coefficients are vendored from OpenPowerlifting's published source, with test vectors. Recorded caveat: DOTS is calibrated on powerlifting S/B/D, which is why eligibility is restricted.
   - **Normalisation inputs**: bodyweight = nearest `BodyMetric` weight within 30 days of the qualifying set; missing fresh bodyweight, or missing `sex` for DOTS, excludes the user from that board with a hint to fill the gap, never an error.
2. **Weekly volume**: per ISO week, ranked by hard sets (`normal` + `dropset`), with tonnage (sum of weight x reps) shown alongside.
3. **Consistency**: current streak (consecutive ISO weeks containing at least one completed session) and sessions in the last 30 days.
4. **Cardio distance**: per activity type, distance summed per ISO week and all-time; entries without distance don't count.

Identity and privacy: boards expose pseudonym-or-name + metric only. Navigating from a board entry to another user's underlying sessions still requires that user's `share_history=True`, friend or not. Ties share a rank.

**Lead-change notices** (confirmed): best-lift lead changes (absolute family) generate in-app notices per section 5.6, surfaced as a feed with an unread badge in the navigation. Both directions fire: taking a lead and losing one. Actor names in notices follow the same friendship rule as boards.

## 8. Screens (mobile-first)

**Interaction rules** (confirmed, apply everywhere):
- **Navigation**: bottom tab bar with four tabs. Home (dashboard), Workout (start / active session / session history), Boards (leaderboards), More (analytics, routines + library, body metrics, cardio, shared history, settings). Notices are a badged bell icon in the top bar on every screen.
- **Set completion**: a dedicated tick target of at least 44px, visually distinct from the row. Tapping elsewhere on the row edits; it never completes.
- **Value entry**: steppers for small adjustments; tapping the value opens a decimal keypad (`inputmode=decimal`) with the current value pre-selected for instant overwrite.
- **Wake lock**: the Screen Wake Lock API holds the screen on during an active session, released on finish or leaving the workout, re-acquired on visibility return. This largely neutralises the accepted lock-screen rest-timer limitation, since the screen doesn't lock mid-session.
- **Glanceability**: extra-large numerals for weight, reps and the timer on the active workout screen.
- **Finish warning**: finishing with unticked planned sets warns once, listing them, before discarding the scaffold.
- **Mistake recovery**: set-level deletes show a 5-second undo toast (restore = clearing `deleted_at`); deleting or discarding a whole session requires a confirm dialog.
- **Dangling sessions**: while a session is unfinished, Home shows a persistent banner. Past 6 hours unfinished, the next app open prompts finish-as-logged or discard. Sessions are never auto-discarded.
- **Exercise picker**: opens showing favourites (starred) then recents, with muscle/equipment filters and search below. In-session swap adds the same-primary-muscle pre-filter.
- **First run**: an account with no sessions and no routines gets a skippable guided setup: units and bodyweight unit, optional volume targets, clone a curated starter routine. Revisitable from settings; never blocks.


1. **Dashboard**: "Next up" card from the rotation, start workout (next up / any routine / freeform / repeat last), this week's session count, weekly volume progress bars against targets, muscle freshness mini-grid, deload week banner/action, bodyweight quick-add, recent PRs.
2. **Active workout**: the screen that matters most, rendered in extra-large numerals. Exercise list from routine with progression suggestion shown per exercise; per-set row: weight stepper (±2.5 kg, long-press ±0.5) with tap-to-type, reps/duration/distance inputs per the exercise metric, L/R toggle on unilateral exercises (with duplicate-to-other-side), RPE picker, warm-up toggle, drop-set button, AMRAP sets shown as "max", and a dedicated tick target to complete. Ghost text shows last session's numbers faintly in each planned row; tapping the exercise name opens a history bottom sheet (recent sessions + PR summary). Ticked sets that beat history flash a PR badge instantly. Rest timer auto-starts on set completion (client JS countdown from `rest_seconds`, vibration + audio cue; wake lock keeps the screen on per the interaction rules). Superset groups render visually grouped; the timer runs `superset_rest_seconds` (or none) between partners and `rest_seconds` after the full round. Per-block actions: swap exercise (search picker, pre-filtered to the same primary muscle with the filter clearable, replaces remaining planned sets for that block), add exercise, and generate warm-up ramp. Plate calculator popover on any weight field for exercises with `bar_weight_kg` set. Finish dialog captures optional session RPE and notes, warning once if planned sets remain unticked. A "log past session" variant of this screen adds a date/time picker and disables the timer.
3. **Session history & detail**: past sessions list; detail view with edited marker where applicable and a "save as routine" action.
4. **Routine builder + library**: search/filter exercise picker (active exercises, filter by muscle/equipment), drag ordering, superset grouping, targets, rest and progression rule per exercise. Library tab browses curated and shared routines with a clone button; rotation ordering managed here.
5. **Exercise detail**: history table, PR summary, e1RM trend chart.
6. **Analytics**: e1RM trend per chosen exercise; weekly volume per muscle group against targets (bars); muscle freshness grid; actual-vs-prescribed rest per exercise; bodyweight trend with optional overlay onto volume/e1RM charts.
7. **Leaderboards**: dedicated nav item; tabs for best lifts (absolute / ratio / DOTS family selector, plus DOTS total), weekly volume, consistency, cardio distance per section 7.
8. **Notices**: feed of lead-change and friend-request notices (accept/decline inline), unread badge in nav, mark-read on view.
9. **Body metrics**: entry form + trend charts.
10. **Cardio**: quick-log form + history.
11. **Shared history** (only where `share_history` is on): read-only view of another user's sessions. Structured data only: session and set free-text notes are never rendered in shared views.
12. **Profile/settings**: units, sex (for DOTS), pseudonym view/regenerate, friends management (add by username, pending requests, remove), share_history toggle, volume targets per muscle group, deload week parameters, export buttons.
13. **First-run setup**: the guided flow per the interaction rules above.
14. **Django admin**: exercise curation, user management, data fixes.

Theme: follows `prefers-color-scheme`; light and dark palettes both built via Tailwind's dark variant.

Charts: server renders data as JSON into the page, small client chart lib (uPlot preferred for size; Chart.js acceptable).

## 9. Deployment

- VM or LXC, systemd unit running gunicorn from a uv-managed venv (confirmed).
- Caddy in front: reverse proxy to gunicorn, automatic ACME TLS, `file_server` for `/media/*`, security headers, optional IP restriction on the admin path.
- SQLite file + media dir on local disk; nightly backup = `sqlite3 .backup` or `VACUUM INTO` plus rsync into the existing backup routine. WAL means no raw file copy while hot.
- `DEBUG=False` everywhere but dev.
- No health endpoint or Zabbix integration (offered, declined). systemd `Restart=on-failure` is the only supervision.

## 10. Build order

1. Project scaffold, auth, profile, SQLite WAL config, hardening settings, Tailwind pipeline.
2. Exercise import (data + images) + MuscleGroup mapping + admin curation.
3. Routine builder including progression rule fields, rotation ordering, curated routine fixture.
4. Active workout logging (the core loop): planned-set scaffold, completion writes, per-metric inputs, unilateral L/R, AMRAP display, ghost text + history sheet, live PR flash, favourites-first picker, extras, in-session swap/add, warm-up ramp generator, backdated entry, rest timer, plate calculator.
5. Progression suggestion engine including stall deload and deload week mode.
6. Session history & detail, post-finish editing with `edited_at`, save-as-routine, exercise detail, PRs/e1RM.
7. Body metrics + cardio.
8. Analytics dashboard: volume vs targets, freshness grid, rest analytics, trends.
9. Per-user export (CSV/JSON).
10. Friends, pseudonyms, and identity display rules.
11. Leaderboards: absolute, ratio, and DOTS families plus DOTS total.
12. Lead-change notices + feed (including friend-request notices).
13. Opt-in shared history view.
14. Guided first-run setup.
15. PWA manifest + service worker shell.
16. Caddy + systemd deployment.
17. (v2) Offline queue; optional 2FA.

## 11. Resolved defaults

Accepted without objection during review:
- Routine sharing is owner-set private/shared flag with clone-on-adopt.
- Secondary-muscle volume factor 0.5 (configurable).
- Rest timer lock-screen limitation accepted for v1.

Deliberate scope cuts (confirmed):
- Tempo prescriptions live in the notes field; no dedicated tempo schema.
- Exercise variants (flat/paused/close-grip) stay fully separate; no variant-family linking.
- RIR display mode not offered; RPE 6-10 only.
