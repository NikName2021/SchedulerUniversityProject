import io
import re

import pandas as pd


def parse_streams_content(file_bytes: bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), skiprows=3)

    # Normalize column names
    df.columns = [str(col).replace("\n", " ").strip() for col in df.columns]

    streams_map = {}

    for idx, row in df.iterrows():
        event_name = str(row.get("Мероприятие", "")).strip()
        if not event_name or event_name == "nan":
            continue

        raw_type = str(row.get("Вид потока", "")).strip().upper()

        if raw_type == "П":
            stream_type = "Семинар"
        elif raw_type == "З":
            stream_type = "Зачет"
        elif raw_type == "ЛБ":
            stream_type = "Лабораторная"
        elif raw_type == "Л":
            stream_type = "Лекция"
        else:
            stream_type = "Внеучебное мероприятие"

        teacher_raw = str(row.get("Преподаватель", "")).strip()
        teacher_clean = None
        if teacher_raw and teacher_raw != "nan":
            teacher_clean = re.sub(r"\(.*?\)", "", teacher_raw).strip()

        key = (event_name, stream_type)

        # Extract hours/lessons
        # Try to find a column with lessons count
        lessons_raw = (
            row.get("Событий в расп.") or row.get("Кол-во пар") or row.get("Занятий")
        )

        # Fallback to hours if lessons count is not found
        if pd.isna(lessons_raw):
            hours_raw = row.get("Нагрузка") or row.get("Часы") or 2
            try:
                hours = float(hours_raw)
                lessons = max(1, int(hours // 2))
            except:
                lessons = 1
        else:
            try:
                lessons = int(float(lessons_raw))
            except:
                lessons = 1

        lessons = max(1, lessons)

        groups_raw = str(row.get("Группа", "")).strip()
        groups_parsed = []
        if groups_raw and groups_raw != "nan":
            matches = re.finditer(r"([А-Яа-яA-Za-z0-9\-\/]+)\s*\[(\d+)\]", groups_raw)
            for m in matches:
                groups_parsed.append(
                    {"name": m.group(1).strip(), "size": int(m.group(2))}
                )

        if not groups_parsed and groups_raw and groups_raw != "nan":
            groups_parsed = [{"name": groups_raw, "size": 0}]

        if key not in streams_map:
            streams_map[key] = {
                "event": event_name,
                "type": stream_type,
                "teacher": teacher_clean,
                "lessons_count": lessons,
                "groups": [],
            }

        existing_group_names = {g["name"] for g in streams_map[key]["groups"]}
        for g in groups_parsed:
            if g["name"] not in existing_group_names:
                streams_map[key]["groups"].append(g)
                existing_group_names.add(g["name"])

    return list(streams_map.values())
