import pandas as pd
import json
import re


DAY_COLUMNS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота"
]


def parse_lessons(value):
    """
    Преобразует значение ячейки в список.
    Примеры:
      '2,3,4' -> [2, 3, 4]
      'все' -> 'all'
      '' / NaN -> []
    """
    if pd.isna(value):
        return []

    value = str(value).strip().lower()

    if not value:
        return []

    if value == "все":
        return "all"

    # Оставляем только цифры и запятые
    parts = [x.strip() for x in value.split(",") if x.strip()]
    result = []

    for part in parts:
        match = re.search(r"\d+", part)
        if match:
            result.append(int(match.group()))

    return result


def normalize_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def row_to_json(row):
    return {
        "id": normalize_value(row.get("№")),
        "teacher": normalize_value(row.get("ФИО преподавателя")),
        "subject": normalize_value(row.get("дисциплина")),
        "schedule": {
            day: parse_lessons(row.get(day))
            for day in DAY_COLUMNS
        },
        "comment": normalize_value(row.get("комментарий")),
        "email": normalize_value(row.get("почта")),
        "phone": normalize_value(row.get("телефон"))
    }


def convert_table_to_json(input_file, output_file):
    # Для CSV:
    if input_file.endswith(".csv"):
        df = pd.read_csv(input_file)
    else:
        # Для Excel
        df = pd.read_excel(input_file)

    data = [row_to_json(row) for _, row in df.iterrows()]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Готово: {output_file}")


if __name__ == "__main__":
    convert_table_to_json("teachers.xlsx", "teachers.json")