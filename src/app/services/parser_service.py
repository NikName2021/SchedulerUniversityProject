import pandas as pd
import re
import io

def parse_streams_content(file_bytes: bytes):
    df = pd.read_excel(io.BytesIO(file_bytes), skiprows=3)

    # Normalize column names
    df.columns = [str(col).replace('\n', ' ').strip() for col in df.columns]

    streams = []
    
    for idx, row in df.iterrows():
        event_name = str(row.get('Мероприятие', '')).strip()
        if not event_name or event_name == 'nan':
            continue
            
        stream_type = str(row.get('Вид потока', '')).strip()
        
        # Rule 2: Ignore extracurricular
        if stream_type.lower() == 'внеучебное мероприятие':
            continue
            
        # Rule 3: Teacher - extract name outside parentheses
        teacher_raw = str(row.get('Преподаватель', '')).strip()
        teacher_clean = None
        if teacher_raw and teacher_raw != 'nan':
            teacher_clean = re.sub(r'\(.*?\)', '', teacher_raw).strip()
            
        # Parse groups
        groups_raw = str(row.get('Группа', '')).strip()
        groups_parsed = []
        if groups_raw and groups_raw != 'nan':
            matches = re.finditer(r'([А-Яа-яA-Za-z0-9\-\/]+)\s*\[(\d+)\]', groups_raw)
            for m in matches:
                groups_parsed.append({
                    "name": m.group(1).strip(),
                    "size": int(m.group(2))
                })
        
        if not groups_parsed and groups_raw and groups_raw != 'nan':
             groups_parsed = [{"name": groups_raw, "size": 0}]
             
        streams.append({
            "event": event_name,
            "type": stream_type,
            "teacher": teacher_clean,
            "groups": groups_parsed
        })
        
    return streams
