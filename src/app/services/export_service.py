import datetime
import io

import pandas as pd
from database.all_models import ScheduleEntry
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import select
from sqlalchemy.orm import selectinload

WEEK = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}

COLORS = {
    "Лекция": "4472C4",
    "Семинар": "70AD47",
    "Лабораторная": "70AD47",
    "yellow": "FFD966",
    "red": "FF0000",
}


async def generate_excel_report(session, task_id: int | None = None):
    stmt = select(ScheduleEntry).options(selectinload(ScheduleEntry.teacher))
    if task_id:
        stmt = stmt.filter(ScheduleEntry.task_id == task_id)

    stmt = stmt.order_by(ScheduleEntry.date, ScheduleEntry.lesson_number)
    result = await session.execute(stmt)
    entries = result.scalars().all()

    if not entries:
        return None

    rows = []
    for ev in entries:
        if ev.date is None:
            continue
        wd = ev.date.weekday()
        subject_str = f"{ev.event_name} ({ev.stream_type})\n{ev.teacher.name if ev.teacher else ''}\nАуд: {ev.room_id or ''}"

        rows.append(
            {
                "date": ev.date.strftime("%Y-%m-%d"),
                "weekday": WEEK[wd],
                "lesson": ev.lesson_number,
                "group": ev.group_name,
                "subject": subject_str,
                "type": ev.stream_type,
                "warning": ev.warning or "",
            }
        )

    df = pd.DataFrame(rows)

    all_dates = sorted(df["date"].unique())
    all_lessons = [1, 2, 3, 4, 5, 6]

    slots_tuples = []
    for d_str in all_dates:
        d_obj = datetime.datetime.strptime(d_str, "%Y-%m-%d")
        for lesson_number in all_lessons:
            slots_tuples.append((d_str, WEEK[d_obj.weekday()], lesson_number))

    all_slots_idx = pd.MultiIndex.from_tuples(
        slots_tuples, names=["date", "weekday", "lesson"]
    )

    pivot_subject = (
        df.pivot_table(
            index=["date", "weekday", "lesson"],
            columns="group",
            values="subject",
            aggfunc="first",
        )
        .reindex(all_slots_idx)
        .reset_index()
    )
    pivot_type = (
        df.pivot_table(
            index=["date", "weekday", "lesson"],
            columns="group",
            values="type",
            aggfunc="first",
        )
        .reindex(all_slots_idx)
        .reset_index()
    )
    pivot_warning = (
        df.pivot_table(
            index=["date", "weekday", "lesson"],
            columns="group",
            values="warning",
            aggfunc="first",
        )
        .reindex(all_slots_idx)
        .reset_index()
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="raw", index=False)
        ws = writer.book.create_sheet("Расписание")

        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        header_row = 1
        data_start_row = 2
        data_start_col = 4

        group_cols = pivot_type.columns[3:]
        current_row_idx = data_start_row
        prev_date = None

        for i in range(len(pivot_type)):
            row_type = pivot_type.iloc[i]
            row_subj = pivot_subject.iloc[i]
            row_warn = pivot_warning.iloc[i]

            current_date = row_type["date"]

            if prev_date is not None and current_date != prev_date:
                for j in range(3 + len(group_cols)):
                    cell = ws.cell(row=current_row_idx, column=j + 1)
                    cell.fill = PatternFill(
                        start_color="DDDDDD", end_color="DDDDDD", fill_type="solid"
                    )
                current_row_idx += 1

            prev_date = current_date

            for j in range(3):
                cell = ws.cell(row=current_row_idx, column=j + 1)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")
                if j == 0:
                    cell.value = row_type["date"]
                elif j == 1:
                    cell.value = row_type["weekday"]
                elif j == 2:
                    cell.value = row_type["lesson"]

            for j, group in enumerate(group_cols):
                c_type = row_type[group]
                c_warn = row_warn[group]
                c_subj = row_subj[group]

                cell = ws.cell(row=current_row_idx, column=data_start_col + j)
                cell.border = thin_border
                cell.alignment = Alignment(
                    horizontal="center", vertical="center", wrap_text=True
                )

                if pd.notna(c_type):
                    bg_color = COLORS.get(c_type, "CCCCCC")
                    text_color = "FFFFFF"

                    if pd.notna(c_warn) and c_warn:
                        if "Нет аудитории" in str(c_warn):
                            bg_color = COLORS["red"]
                        else:
                            bg_color = COLORS["yellow"]
                            text_color = "000000"

                    cell.fill = PatternFill(
                        start_color=bg_color, end_color=bg_color, fill_type="solid"
                    )
                    cell.font = Font(color=text_color, bold=True)

                    val = str(c_subj)
                    if pd.notna(c_warn) and c_warn:
                        val += f"\n⚠️ {c_warn}"
                    cell.value = val

            current_row_idx += 1

        for j, col_name in enumerate(pivot_type.columns):
            cell = ws.cell(row=header_row, column=j + 1)
            cell.value = {"date": "Дата", "weekday": "День", "lesson": "Пара"}.get(
                col_name, col_name
            )
            cell.fill = PatternFill(
                start_color="333333", end_color="333333", fill_type="solid"
            )
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border

        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 8

    output.seek(0)
    return output
