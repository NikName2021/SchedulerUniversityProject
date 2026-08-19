import io
import re
import zipfile
from pathlib import Path

import pandas as pd

from services.group_relation_service import parse_group_label

MAX_TABLE_ROWS = 50_000
MAX_TABLE_COLUMNS = 200
MAX_WORKBOOK_FILES = 10_000
MAX_WORKBOOK_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


def _validate_xlsx_archive(file_bytes: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            members = archive.infolist()
            if len(members) > MAX_WORKBOOK_FILES:
                raise ValueError("Workbook contains too many files")
            unpacked_size = sum(member.file_size for member in members)
            if unpacked_size > MAX_WORKBOOK_UNCOMPRESSED_BYTES:
                raise ValueError("Workbook expands beyond the allowed size")
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid XLSX workbook") from exc


def read_tabular_content(
    file_bytes: bytes, filename: str, *, skiprows: int = 0
) -> pd.DataFrame:
    extension = Path(filename).suffix.lower()
    if extension == ".csv":
        decode_error: UnicodeDecodeError | None = None
        for encoding in ("utf-8-sig", "cp1251"):
            try:
                text = file_bytes.decode(encoding)
                dataframe = pd.read_csv(
                    io.StringIO(text),
                    sep=None,
                    engine="python",
                    skiprows=skiprows,
                )
                break
            except UnicodeDecodeError as exc:
                decode_error = exc
        else:
            raise ValueError("CSV encoding must be UTF-8 or Windows-1251") from decode_error
    else:
        if extension == ".xlsx":
            _validate_xlsx_archive(file_bytes)
        dataframe = pd.read_excel(io.BytesIO(file_bytes), skiprows=skiprows)

    if len(dataframe.index) > MAX_TABLE_ROWS:
        raise ValueError(f"Table exceeds the {MAX_TABLE_ROWS} row limit")
    if len(dataframe.columns) > MAX_TABLE_COLUMNS:
        raise ValueError(f"Table exceeds the {MAX_TABLE_COLUMNS} column limit")
    return dataframe


def _read_streams_table(file_bytes: bytes, filename: str) -> pd.DataFrame:
    initial_skiprows = 0 if Path(filename).suffix.lower() == ".csv" else 3
    dataframe = read_tabular_content(
        file_bytes, filename, skiprows=initial_skiprows
    )
    normalized = {
        str(column).replace("\n", " ").strip() for column in dataframe.columns
    }
    if "Мероприятие" not in normalized:
        fallback_skiprows = 3 if initial_skiprows == 0 else 0
        dataframe = read_tabular_content(
            file_bytes, filename, skiprows=fallback_skiprows
        )
    return dataframe


def parse_streams_content(file_bytes: bytes, filename: str = "streams.xlsx") -> list[dict]:
    df = _read_streams_table(file_bytes, filename)

    # Normalize column names
    df.columns = [str(col).replace("\n", " ").strip() for col in df.columns]
    required_columns = {"Мероприятие", "Группа"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    streams_map: dict[tuple[str, str, str | None], dict] = {}

    for _idx, row in df.iterrows():
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

        key = (event_name, stream_type, teacher_clean)

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
            except (TypeError, ValueError):
                lessons = 1
        else:
            try:
                lessons = int(float(lessons_raw))
            except (TypeError, ValueError):
                lessons = 1

        lessons = max(1, lessons)

        groups_raw = str(row.get("Группа", "")).strip()
        groups_parsed = []
        if groups_raw and groups_raw != "nan":
            matches = list(
                re.finditer(r"([А-Яа-яA-Za-z0-9\-\/]+)\s*\[(\d+)\]", groups_raw)
            )
            label_without_sizes = re.sub(r"\s*\[\d+\]", "", groups_raw).strip()
            parsed_label = parse_group_label(label_without_sizes)
            if matches and (parsed_label.is_joint or parsed_label.subgroup):
                groups_parsed = [
                    {
                        "name": label_without_sizes,
                        "size": sum(int(match.group(2)) for match in matches),
                    }
                ]
            else:
                for match in matches:
                    groups_parsed.append(
                        {
                            "name": match.group(1).strip(),
                            "size": int(match.group(2)),
                        }
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

        existing_groups = {
            group["name"]: group for group in streams_map[key]["groups"]
        }
        for g in groups_parsed:
            existing = existing_groups.get(g["name"])
            if existing is None:
                streams_map[key]["groups"].append(g)
                existing_groups[g["name"]] = g
            else:
                existing["size"] = max(existing["size"], g["size"])

    return list(streams_map.values())
