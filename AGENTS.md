# AGENTS.md — Smart Scheduler project guidelines

These instructions apply to the entire repository. Keep the application
consistent with the current architecture and with the Russian operator UI.

## Technology stack

- Backend: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0 async.
- Database: PostgreSQL in production, SQLite for local development and tests,
  Alembic for schema migrations.
- Scheduling: Google OR-Tools CP-SAT.
- Background work: Celery with Redis.
- Frontend: React 19, TypeScript, Vite, Zustand, Tailwind CSS v4.
- Icons: `lucide-react`.
- Import/export: Pandas, OpenPyXL, CSV/XLS/XLSX.

## Source-of-truth paths

- `src/app/database/all_models.py`: SQLAlchemy models.
- `src/app/api/routes/`: active FastAPI routers.
- `src/app/services/`: business logic, import/export, scheduling and quality.
- `src/app/services/scheduler_engine.py`: base CP-SAT engine.
- `src/app/services/scalable_scheduler.py`: scalable scheduling engine.
- `src/app/schemas/planning.py` and `reference.py`: active Pydantic schemas.
- `src/app/migrations/versions/`: Alembic revisions.
- `spa/src/pages/`: React pages.
- `spa/src/store/useAppStore.ts`: shared Zustand state.
- `spa/src/utils/scheduleTime.ts`: canonical seven-pair timetable.
- `spa/src/utils/openDownload.ts`: safe download-window helper.
- `AUDIT_REPORT.md`: latest audit findings and accepted risks.

The former JWT/Telegram prototype, repositories and authentication helpers were
removed. Do not reintroduce imports from `helpers`, `repositories`,
`schemas.input_forms`, `schemas.response`, `user_service` or
`user_service_tg`.

## Architecture and security boundary

- The active API currently has no built-in authentication or RBAC.
- UI role labels are descriptive only and must never be treated as access
  control.
- Until a dedicated, tested RBAC implementation exists, deployment must remain
  behind an authenticated reverse proxy in a closed network.
- Do not add ad-hoc JWT or Telegram authentication helpers. Authentication
  requires an explicit feature design, current SQLAlchemy models, Alembic
  migrations, Pydantic schemas and API tests.
- Never expose internal exception text in API responses. Log the exception and
  return a stable generic message.
- Preserve `TrustedHostMiddleware`, explicit CORS origins, security headers,
  Nginx request limits and loopback-only database/backend port bindings.

## Scheduling invariants

- The week is Monday through Sunday.
- There are exactly seven lesson slots. Reuse `PAIR_TIMES` on the frontend and
  validate backend lesson numbers in the range `1..7`.
- Validate teacher, student-group and room overlaps before every manual or
  generated schedule write.
- A shared stream is identified by `source_stream_id`; it must not conflict
  with itself across its participating groups.
- An unassigned room is not a physical room and must not create a room
  conflict.
- Fixed lessons, holidays, availability rules and room requirements are hard
  constraints unless a rule profile explicitly defines otherwise.
- Manual changes must be reflected in quality metrics, lifecycle revisions and
  Excel export.

## Backend conventions

- Add type hints to every function signature.
- Use `AsyncSession`, SQLAlchemy `select()` and explicit transactions.
- API endpoints should use Pydantic request/response models and
  `fastapi.HTTPException` for expected failures.
- Validate collection sizes, date ranges and solver resource settings at the
  API boundary.
- Keep uploads bounded and streamed. Sanitize filenames, restrict extensions,
  validate spreadsheet dimensions/ZIP expansion and remove failed uploads.
- Neutralize Excel formula prefixes in every exported user-controlled value.
- On background-task preparation failure, mark the task failed and release its
  generation lock.

## Database migrations

- Never use `create_all()` as a production migration mechanism.
- Every model/schema change requires an Alembic revision.
- Keep `DATABASE_SCHEMA_REVISION` in `src/app/core/config.py` synchronized with
  the single Alembic head so `/health/ready` fails closed on schema drift.
- Run both `alembic upgrade head` and `alembic check` after migration changes.
- `alembic stamp 20260716_0001` is only for a verified copy of the original
  pre-Alembic schema; back up the database first.

## Frontend conventions

- Use functional React components with TypeScript.
- Use Zustand for state shared across pages; keep local UI state in components.
- Use Tailwind classes. Inline styles are acceptable only for genuinely dynamic
  positioning or dimensions.
- Build API URLs from `API_BASE_URL`.
- Check `response.ok`, surface a useful Russian error and roll back optimistic
  changes when a request fails.
- Open downloads through `openDownload`; do not call `window.open` directly.
- Interactive icon-only controls need `aria-label` and `title`. Custom grid
  controls must support keyboard activation.
- Keep the interface usable at mobile widths. Wide schedule/calendar grids may
  use local horizontal scrolling, but the page itself must not overflow.
- All user-facing text must be Russian.

## Operator dashboard design

Treat `spa/src/pages/SchedulePage.tsx` as the current schedule design source.
Keep day columns, lesson rows and these card tokens:

- Lecture: `bg-[#e6fffa]`, `border-[#2c7a7b]`.
- Practice/seminar: `bg-[#e0f2fe]`, `border-[#0369a1]`.
- Laboratory: `bg-[#f3e8ff]`, `border-[#7e22ce]`.

Reuse existing Lucide icons and established components before adding new visual
patterns.

## Required verification

From the repository root:

```bash
python -m pytest
python -m ruff check src/app
docker compose --env-file .env.example config --quiet
```

For frontend changes:

```bash
cd spa
npm run validate
npm run build
```

For dependency or security-sensitive changes, also run:

```bash
pip-audit --no-deps --disable-pip -r src/requirements.txt
cd spa && npm audit --omit=dev
```

Add regression tests for every fixed bug. Backend tests belong in
`src/app/tests/`; frontend utility tests belong in `spa/tests/`.

## Repository hygiene

- Do not use placeholder data when real deterministic demonstration data is
  required.
- Keep `spa/package-lock.json` synchronized with `spa/package.json`.
- Do not commit `.env`, databases, uploads, logs, build output or test build
  output.
- Treat existing unrelated changes, `outputs/` and generated deliverables as
  user-owned unless the task explicitly includes them.
- Update README, deployment documentation and `AUDIT_REPORT.md` when behavior,
  operational requirements or accepted risks change.
