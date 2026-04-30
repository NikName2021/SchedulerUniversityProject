import pandas as pd
import re
import json
import os

def parse_streams(file_path: str):
    # Загружаем файл, пропуская первые 3 строки-заголовка
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return []
    
    df = pd.read_excel(file_path, skiprows=3)

    # Нормализуем имена колонок (удаляем переносы строк и пробелы по краям)
    df.columns = [str(col).replace('\n', ' ').strip() for col in df.columns]

    # Колонки для поиска, с учетом возможных вариаций:
    # "Вид потока", "Мероприятие", "Преподаватель", "Группа"
    
    streams = []
    
    for idx, row in df.iterrows():
        # Отфильтровываем пустые строки (например, если нет мероприятия)
        event_name = str(row.get('Мероприятие', '')).strip()
        if not event_name or event_name == 'nan':
            continue
            
        stream_type = str(row.get('Вид потока', '')).strip()
        
        # Правило 2: Внеучебные не расставляются
        if stream_type.lower() == 'внеучебное мероприятие':
            continue
            
        # Правило 3: Преподаватель (отрезаем всё в скобках)
        teacher_raw = str(row.get('Преподаватель', '')).strip()
        teacher_clean = None
        if teacher_raw and teacher_raw != 'nan':
            teacher_clean = re.sub(r'\(.*?\)', '', teacher_raw).strip()
            
        # Распарсинг групп (например: ИОП-ИТ-24/1 [20]ИОП-ИТ-24/2 [22])
        # Regex ищет "(Текст-любой) [цифры]"
        groups_raw = str(row.get('Группа', '')).strip()
        groups_parsed = []
        if groups_raw and groups_raw != 'nan':
            matches = re.finditer(r'([А-Яа-яA-Za-z0-9\-\/]+)\s*\[(\d+)\]', groups_raw)
            for m in matches:
                groups_parsed.append({
                    "name": m.group(1).strip(),
                    "size": int(m.group(2))
                })
        
        # Если регулярка не сработала, но в группе есть просто название без скобок
        if not groups_parsed and groups_raw and groups_raw != 'nan':
             # Попробуем разделить по переносу строки или пробелу (на всякий случай)
             groups_parsed = [{"name": groups_raw, "size": 0}]
             
        # Правило 1: Главное название - Мероприятие
        streams.append({
            "event": event_name,
            "type": stream_type,
            "teacher": teacher_clean,
            "groups": groups_parsed
        })
        
    return streams

if __name__ == "__main__":
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Потоки обучающихся (8).xls')
    parsed_data = parse_streams(file_path)
    
    output_path = os.path.join(os.path.dirname(__file__), 'parsed_streams.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)
        
    print(f"Успешно обработано {len(parsed_data)} потоков. Сохранено в {output_path}")
    if len(parsed_data) > 0:
        print("\nПример (первые 2):")
        print(json.dumps(parsed_data[:2], ensure_ascii=False, indent=2))
