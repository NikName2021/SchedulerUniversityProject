import openpyxl
import json


def parse_excel_to_json(input_file, output_file="output.json"):
    # Загружаем Excel-файл (data_only=True позволяет читать итоговые значения, а не сами формулы, если они есть)
    try:
        workbook = openpyxl.load_workbook(input_file, data_only=True)
    except FileNotFoundError:
        return f"Файл {input_file} не найден."

    sheet = workbook.active
    result = {}

    # Итерируемся по строкам на листе
    for row in sheet.iter_rows(values_only=True):
        # Пропускаем пустые строки или строки, где недостаточно колонок
        if not row or len(row) < 6:
            continue

        # Индекс 1 — это колонка 'B' (Название предмета)
        name = row[1]

        # Пропускаем пустые названия и строки с заголовком таблицы
        if not name or str(name).strip() == "Название":
            continue

        # Индексы 3, 4, 5 — это колонки 'D', 'E', 'F' (Лекции, Лаб. зан-я, Практ. зан-я)
        lec = str(row[3]) if row[3] is not None else "0"
        lab = str(row[4]) if row[4] is not None else "0"
        prac = str(row[5]) if row[5] is not None else "0"

        # Очищаем данные от скобок (например, превращаем "34(16)" в "34")
        lec_val = lec.split('(')[0].strip()
        lab_val = lab.split('(')[0].strip()
        prac_val = prac.split('(')[0].strip()

        result[name.split('(')[0]] = {
            "Лекции": int(lec_val) if lec_val.isdigit() else 0,
            "Лабораторные": int(lab_val) if lab_val.isdigit() else 0,
            "Семинары": int(prac_val) if prac_val.isdigit() else 0
        }

    # Формируем JSON-строку с отступами для красоты
    json_data = json.dumps(result, ensure_ascii=False, indent=4)

    # Сохраняем результат в файл
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(json_data)

    return json_data


# === Запуск программы ===
# Замени 'plan.xlsx' на путь к твоему Excel-файлу
excel_file_path = 'plan.xlsx'

print("Начинаю обработку файла...")
output_json = parse_excel_to_json(excel_file_path)
print("\nРезультат:")
print(output_json)
print("\nДанные также сохранены в файл output.json")