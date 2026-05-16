# AGENTS.md - Project Guidelines for AI Assistants

This document contains rules and patterns for AI assistants working on the "Умное Расписание" (Smart Scheduler) project. Follow these strictly to maintain consistency.

## 🛠 Tech Stack
- **Backend**: FastAPI, SQLAlchemy 2.0 (PostgreSQL), Pydantic v2.
- **Frontend**: React (Vite), Zustand (State Management), TailwindCSS (Styling).
- **Automation**: Google OR-Tools (Scheduler Engine).

## 🏗 Project Structure
- `src/app/database/`: Database models (`all_models.py`) and connection logic.
- `src/app/api/routes/`: FastAPI endpoints.
- `src/app/scheduler/`: Core scheduling engine and logic.
- `spa/src/pages/`: React page components.
- `spa/src/store/`: Zustand stores.

## 🎨 Design System (Operator Dashboard)
Follow the design of `Расписание.html`:
- **Grid Layout**: Columns for days (ПН-ВС), rows for time slots.
- **Card Colors**:
  - Lecture: `bg-[#e6fffa]` (Teal 50), Border: `border-[#2c7a7b]`.
  - Practice: `bg-[#e0f2fe]` (Sky 50), Border: `border-[#0369a1]`.
  - Laboratory: `bg-[#f3e8ff]` (Purple 50), Border: `border-[#7e22ce]`.
- **Icons**: Use standard SVG icons from Heroicons (matching the existing UI).

## 🐍 Python Coding Standards
- Use **Type Hints** for all function signatures.
- **SQLAlchemy**: Use `AsyncSession` and `select()` statements (2.0 style).
- **API**: Endpoints must return Pydantic models. Use `fastapi.HTTPException` for errors.

## ⚛ React Coding Standards
- **Components**: Functional components with TypeScript.
- **State**: Prefer Zustand for shared state (e.g., current schedule data).
- **Styling**: Pure TailwindCSS. Avoid inline styles unless dynamic (e.g., positioning cards).
- **Data Fetching**: Use standard `fetch` or a custom hook.

## 📋 Best Practices
1. **Never use placeholders**: Generate real demonstration data if needed.
2. **Conflict Detection**: Always validate time/teacher/room overlaps before committing database changes.
3. **Excel Compatibility**: Manual edits must be reflected in the Excel export functionality.
4. **Localization**: Use Russian for the user interface as per project requirements.
