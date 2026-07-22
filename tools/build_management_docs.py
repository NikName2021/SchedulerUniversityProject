"""Build the management documentation package for Smart Scheduler.

The documents are generated from the current application architecture (models,
routes, Compose configuration, and UI) as of 22 July 2026.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT = Path("deliverables/Документация_Умное_Расписание")
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
INK = "0B2545"
PALE_BLUE = "E8EEF5"
PALE_GRAY = "F2F4F7"
MUTED = "667085"
TABLE_WIDTH = 9360


def set_cell_shading(cell: object, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()  # type: ignore[attr-defined]
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_width(cell: object, width: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()  # type: ignore[attr-defined]
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width))
    tc_w.set(qn("w:type"), "dxa")


def set_table_geometry(table: object, widths: Sequence[int]) -> None:
    table.autofit = False  # type: ignore[attr-defined]
    table.alignment = WD_TABLE_ALIGNMENT.LEFT  # type: ignore[attr-defined]
    tbl_pr = table._tbl.tblPr  # type: ignore[attr-defined]
    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    indent = tbl_pr.first_child_found_in("w:tblInd")
    if indent is None:
        indent = OxmlElement("w:tblInd")
        tbl_pr.append(indent)
    indent.set(qn("w:w"), "120")
    indent.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid  # type: ignore[attr-defined]
    for col, width in zip(grid.gridCol_lst, widths):
        col.set(qn("w:w"), str(width))
    for row in table.rows:  # type: ignore[attr-defined]
        for cell, width in zip(row.cells, widths):
            set_cell_width(cell, width)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def set_repeat_table_header(row: object) -> None:
    tr_pr = row._tr.get_or_add_trPr()  # type: ignore[attr-defined]
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def set_cell_margins(cell: object, top: int = 80, start: int = 120, bottom: int = 80, end: int = 120) -> None:
    tc = cell._tc  # type: ignore[attr-defined]
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_run(run: object, size: float = 11, bold: bool = False, color: str = "000000", italic: bool = False) -> None:
    run.font.name = "Calibri"  # type: ignore[attr-defined]
    run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")  # type: ignore[attr-defined]
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")  # type: ignore[attr-defined]
    run.font.size = Pt(size)  # type: ignore[attr-defined]
    run.font.color.rgb = RGBColor.from_string(color)  # type: ignore[attr-defined]
    run.bold = bold  # type: ignore[attr-defined]
    run.italic = italic  # type: ignore[attr-defined]


def add_page_field(paragraph: object) -> None:
    run = paragraph.add_run("Страница ")  # type: ignore[attr-defined]
    set_run(run, size=9, color=MUTED)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)  # type: ignore[attr-defined]


def configure_document(doc: Document, title: str, subtitle: str) -> None:
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.49)
    section.footer_distance = Inches(0.49)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1
    for name, size, color, before, after in (
        ("Heading 1", 16, BLUE, 16, 8),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DARK_BLUE, 8, 4),
    ):
        style = styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
    for name in ("List Bullet", "List Number"):
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.1

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = header.add_run("УМНОЕ РАСПИСАНИЕ  |  ")
    set_run(run, size=9, bold=True, color=BLUE)
    run = header.add_run(subtitle.upper())
    set_run(run, size=9, color=MUTED)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_page_field(footer)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(36)
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(title)
    set_run(r, size=25, bold=True, color=INK)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(18)
    r = p.add_run(subtitle)
    set_run(r, size=14, color=MUTED)
    meta = doc.add_table(rows=3, cols=2)
    set_table_geometry(meta, [2100, 7260])
    for row, (key, value) in zip(meta.rows, (("Версия", "1.0"), ("Дата", "22 июля 2026 г."), ("Основание", "Актуальная структура исходного кода проекта"))):
        for cell in row.cells:
            set_cell_margins(cell)
        set_cell_shading(row.cells[0], PALE_BLUE)
        p1 = row.cells[0].paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        set_run(p1.add_run(key), bold=True, color=DARK_BLUE)
        p2 = row.cells[1].paragraphs[0]
        p2.paragraph_format.space_after = Pt(0)
        set_run(p2.add_run(value))
    doc.add_paragraph()


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def add_text(doc: Document, text: str, bold_lead: str | None = None) -> None:
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        set_run(p.add_run(bold_lead), bold=True, color=INK)
        set_run(p.add_run(text[len(bold_lead):]))
    else:
        set_run(p.add_run(text))


def add_bullets(doc: Document, items: Iterable[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        set_run(p.add_run(item))


def add_numbers(doc: Document, items: Iterable[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Number")
        set_run(p.add_run(item))


def add_table(doc: Document, headers: Sequence[str], rows: Sequence[Sequence[str]], widths: Sequence[int] | None = None, font_size: float = 9) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    if widths is None:
        widths = [TABLE_WIDTH // len(headers)] * len(headers)
    set_table_geometry(table, widths)
    header = table.rows[0]
    set_repeat_table_header(header)
    for cell, value in zip(header.cells, headers):
        set_cell_shading(cell, PALE_BLUE)
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        set_run(p.add_run(value), size=font_size, bold=True, color=DARK_BLUE)
    for data in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, data):
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            set_run(p.add_run(value), size=font_size)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_note(doc: Document, label: str, text: str) -> None:
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [TABLE_WIDTH])
    cell = table.cell(0, 0)
    set_cell_shading(cell, PALE_GRAY)
    set_cell_margins(cell, top=120, bottom=120)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    set_run(p.add_run(f"{label}. "), bold=True, color=DARK_BLUE)
    set_run(p.add_run(text))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_contents(doc: Document, items: Sequence[str]) -> None:
    add_heading(doc, "Содержание", 1)
    for item in items:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        set_run(p.add_run(item), color=DARK_BLUE)


def build_database_document() -> Path:
    doc = Document()
    configure_document(doc, "Архитектура базы данных", "Техническое описание структуры данных")
    add_contents(doc, [
        "1. Назначение и границы", "2. Логическая модель", "3. Каталог таблиц",
        "4. Связи и целостность", "5. Индексы и эксплуатационные правила",
    ])
    add_heading(doc, "1. Назначение и границы")
    add_text(doc, "Документ описывает прикладную модель данных системы «Умное Расписание». Источники: src/app/database/all_models.py и миграции Alembic 20260716_0001—20260720_0006. PostgreSQL является промышленной СУБД; SQLite допускается конфигурацией только для локальной разработки.")
    add_note(doc, "Статус схемы", "Состав таблиц ниже соответствует модели приложения на дату документа. В промышленной среде фактическая структура определяется миграциями Alembic, применёнными до revision head.")
    add_heading(doc, "2. Логическая модель")
    add_text(doc, "Модель разделена на пять доменов: справочники ресурсов; импорт и учебная нагрузка; календарное планирование; расчёт и диагностика; итоговое расписание.")
    add_table(doc, ["Домен", "Основные сущности", "Назначение"], [
        ("Справочники", "department, building, room, room_feature, activity_type, discipline", "Единые данные о подразделениях, аудиториях, типах занятий и дисциплинах."),
        ("Учебные данные", "import_batch, teacher, stream, stream_group, student_group", "Партии импорта, преподаватели, потоки занятий и состав групп."),
        ("Правила", "availability_rule, rule_profile, rule_setting", "Доступность участников и настраиваемые правила оптимизации."),
        ("Планирование", "academic_period, planning_week, weekly_lesson_demand", "Семестр, недели и недельная учебная нагрузка."),
        ("Расчёт", "generation_task, generation_component, generation_lock, generation_issue", "Версии расчётов, состояние выполнения, блокировки и диагностика."),
        ("Результат", "schedule_entry", "Строки сформированного или вручную отредактированного расписания."),
    ], [1800, 3600, 3960], 9)
    add_heading(doc, "3. Каталог таблиц")
    add_text(doc, "Обозначения: PK — первичный ключ; FK — внешний ключ; NN — обязательное поле; UQ — уникальность. Типы отражают SQLAlchemy-модель (String в PostgreSQL разворачивается в строковый тип).")

    catalog = [
        ("Справочники", [
            ("department", "Подразделение", "id PK; code UQ; name NN,UQ"),
            ("activity_type", "Тип занятия", "id PK; code NN,UQ; name NN,UQ; room_type; is_shared_for_groups; color; is_active"),
            ("discipline", "Дисциплина", "id PK; full_name NN,UQ; short_name; external_id UQ"),
            ("building", "Корпус", "id PK; code UQ; name NN,UQ; address"),
            ("room", "Аудитория", "id PK; building_id FK; owner_department_id FK; code NN; name; floor; capacity NN; room_type NN; is_active NN"),
            ("room_feature", "Оснащение аудитории", "id PK; code NN,UQ; name NN,UQ"),
            ("room_feature_link", "Связь аудитория—оснащение", "id PK; room_id FK,NN; feature_id FK,NN; UQ(room_id, feature_id)"),
            ("rule_profile", "Профиль правил", "id PK; name NN,UQ; description; education_level; is_default NN; is_active NN"),
            ("rule_setting", "Настройка правила", "id PK; profile_id FK,NN; rule_code NN; enabled NN; is_hard NN; weight NN; UQ(profile_id, rule_code)"),
        ]),
        ("Импорт и учебная нагрузка", [
            ("import_batch", "Партия импорта", "id PK; filename NN; file_path; file_type Enum NN; created_date; status; error_message"),
            ("teacher", "Преподаватель", "id PK; department_id FK; name NN,UQ; position; restrictions_json"),
            ("stream", "Учебный поток", "id PK; import_batch_id FK,NN; teacher_id FK; discipline_id FK; activity_type_id FK; required_room_id FK; event_name NN; stream_type; lessons_count; is_ignored; starts_on; ends_on"),
            ("stream_feature_requirement", "Требование потока к оснащению", "id PK; stream_id FK,NN; feature_id FK,NN; is_hard NN; UQ(stream_id, feature_id)"),
            ("student_group", "Учебная группа", "id PK; name NN,UQ; specialty; course; education_form; student_count NN; min_weekly_lessons; max_weekly_lessons"),
            ("stream_group", "Связь поток—группа", "id PK; stream_id FK,NN; student_group_id FK; group_name NN; group_size NN"),
        ]),
        ("Правила и планирование", [
            ("availability_rule", "Ограничение доступности", "id PK; teacher_id FK; student_group_id FK; room_id FK; is_global NN; rule_kind NN; recurrence NN; weekday; specific_date; starts_on; ends_on; lesson_start NN; lesson_end NN; is_hard NN; weight NN; description"),
            ("academic_period", "Учебный период", "id PK; name NN; period_type NN; education_level; starts_on NN; ends_on NN; status NN; created_at NN"),
            ("planning_week", "Неделя планирования", "id PK; period_id FK,NN; sequence_number NN; starts_on NN; ends_on NN; status NN; UQ(period_id, sequence_number); UQ(period_id, starts_on)"),
            ("weekly_lesson_demand", "Недельная потребность в занятиях", "id PK; week_id FK,NN; stream_id FK,NN; lessons_count NN; priority NN; UQ(week_id, stream_id)"),
        ]),
        ("Расчёт и результат", [
            ("generation_task", "Задание и версия расчёта", "id PK; planning_week_id FK; parent_task_id FK; semester_batch_id; version_number NN; publication_status NN; published_at; canceled_at; edit_revision NN; created_at; status; start_date; end_date; groups_json; holidays_json; settings_json; result_count; error_message; total_components NN; completed_components NN; progress_percent NN; metrics_json; celery_*"),
            ("generation_lock", "Блокировка области расчёта", "scope_key PK; task_id FK,NN; created_at NN"),
            ("generation_issue", "Диагностическое сообщение", "id PK; task_id FK,NN; kind NN; severity NN; message NN; stream_id FK; group_name; date; lesson_number; details_json; created_at NN"),
            ("generation_component", "Компонент расчёта", "id PK; task_id FK,NN; component_key NN; status NN; event_count NN; variable_count NN; constraint_count NN; solve_seconds; objective; error_message; UQ(task_id, component_key)"),
            ("schedule_entry", "Запись расписания", "id PK; task_id FK; planning_week_id FK; source_stream_id FK; group_name NN; event_name NN; stream_type NN; teacher_id FK; room_id; room_ref_id FK; date; lesson_number; warning; is_locked NN; created_at"),
        ]),
    ]
    for group, rows in catalog:
        add_heading(doc, group, 2)
        add_table(doc, ["Таблица", "Назначение", "Ключевые поля"], rows, [1900, 2350, 5110], 8.5)

    add_heading(doc, "4. Связи и целостность")
    add_bullets(doc, [
        "Аудитория относится к корпусу и при необходимости к подразделению; её оснащение задаётся связующей таблицей room_feature_link.",
        "Поток создаётся в составе import_batch, может иметь преподавателя, дисциплину, тип занятия, обязательную аудиторию и требования к оснащению; с группами он связан через stream_group.",
        "Academic_period содержит planning_week, а каждая неделя — независимые weekly_lesson_demand. Такая декомпозиция позволяет рассчитывать семестр последовательностью недель.",
        "Generation_task представляет версию расчёта. В ней хранятся компоненты, блокировки и диагностические сообщения. schedule_entry ссылается на задачу, неделю и исходный поток.",
        "Удаление каскадом применяется для дочерних записей, не имеющих смысла без владельца: элементы оснащения, настройки профиля, потоки партии импорта, недельные требования, компоненты/блокировки/диагностика задачи.",
    ])
    add_heading(doc, "Ограничения целостности", 2)
    add_table(doc, ["Объект", "Контроль"], [
        ("room", "capacity ≥ 0; код аудитории уникален в рамках корпуса."),
        ("student_group", "student_count ≥ 0; наименование группы уникально."),
        ("availability_rule", "Должна быть определена область действия (преподаватель, группа, аудитория либо глобально); диапазон пар корректен; вес 1…10."),
        ("academic_period / planning_week", "Дата окончания не может предшествовать дате начала."),
        ("weekly_lesson_demand", "Одна строка нагрузки для пары «неделя—поток»; число занятий неотрицательно; приоритет 1…10."),
        ("rule_setting", "Одна настройка на код правила в рамках профиля; вес 1…10."),
    ], [2500, 6860], 9)
    add_heading(doc, "5. Индексы и эксплуатационные правила")
    add_table(doc, ["Таблица", "Индекс / назначение"], [
        ("availability_rule", "Индексы по teacher_id, student_group_id и room_id ускоряют выбор ограничений при расчёте."),
        ("stream_group", "ix_stream_group_group_name ускоряет выбор потоков учебной группы."),
        ("generation_task", "Индексы по planning_week_id и semester_batch_id поддерживают журнал расчётов и семестровые серии."),
        ("generation_issue", "Составной (task_id, kind) ускоряет сводную диагностику."),
        ("generation_component", "Составной (task_id, status) ускоряет отображение прогресса."),
        ("schedule_entry", "Индексы по слотам преподавателя, аудитории и группы используются при проверке пересечений."),
    ], [2300, 7060], 9)
    add_note(doc, "Правило администрирования", "Изменять структуру вручную в production не следует. Любое изменение модели должно сопровождаться новой миграцией Alembic, проверкой на копии данных и резервным копированием PostgreSQL перед применением.")
    path = OUTPUT / "01_Архитектура_базы_данных.docx"
    doc.save(path)
    return path


def build_user_document() -> Path:
    doc = Document()
    configure_document(doc, "Руководство пользователя", "Работа в операторской системе")
    add_contents(doc, [
        "1. Назначение и роли", "2. Рабочий процесс", "3. Исходные данные и справочники",
        "4. Планирование и расчёт", "5. Проверка, редактирование и публикация", "6. Частые ситуации",
    ])
    add_heading(doc, "1. Назначение и роли")
    add_text(doc, "«Умное Расписание» помогает оператору подготовить исходные учебные данные, настроить ограничения, сформировать расписание, проверить результат, внести допустимые ручные правки и выгрузить утверждённую версию в Excel.")
    add_table(doc, ["Роль", "Ответственность"], [
        ("Оператор расписания", "Импортирует данные, настраивает календарь и правила, запускает расчёты, проверяет результат, вносит правки."),
        ("Администратор справочников", "Поддерживает аудитории, оснащение, типы занятий, дисциплины, профили правил и доступность."),
        ("Руководитель / согласующий", "Проверяет опубликованную версию и использует выгрузку Excel."),
    ], [2600, 6760], 9)
    add_heading(doc, "2. Рабочий процесс")
    add_numbers(doc, [
        "Откройте «Исходные данные» и загрузите файл учебной нагрузки в формате XLS, XLSX или CSV.",
        "В «Учебных потоках» проверьте состав дисциплин, групп, преподавателей и число занятий; исключите из расчёта ненужные потоки.",
        "В «Справочниках» убедитесь, что активны необходимые аудитории, указана вместимость и оснащение, а у типов занятий заданы требования к аудиториям.",
        "В «Календаре» создайте учебный период, недели и ограничения доступности для преподавателей, групп, аудиторий или университета.",
        "В «Расчётах» распределите нагрузку по неделям, задайте приоритеты и праздничные дни, затем запустите расчёт.",
        "В «Расписании» изучите сетку, предупреждения и конфликты. При необходимости отредактируйте записи и зафиксируйте важные занятия.",
        "В «Журнале операций» опубликуйте согласованную версию. После публикации используйте экспорт Excel для выдачи расписания.",
    ])
    add_heading(doc, "3. Исходные данные и справочники")
    add_heading(doc, "3.1 Импорт учебных данных", 2)
    add_text(doc, "Раздел «Исходные данные» хранит историю загрузок. Импорт создаёт партию данных и связанные учебные потоки. Перед загрузкой убедитесь, что файл содержит актуальные группы, дисциплины, преподавателей и учебную нагрузку.")
    add_bullets(doc, [
        "Поддерживаются файлы .xls, .xlsx и .csv. Файлы другого типа отклоняются системой.",
        "После загрузки проверьте число добавленных потоков и групп, затем откройте историю импорта.",
        "Удаление партии импорта предназначено для ошибочной загрузки: связанные потоки удаляются вместе с партией. Не удаляйте исходную партию, если на ней уже основана согласуемая версия расписания.",
    ])
    add_heading(doc, "3.2 Учебные потоки", 2)
    add_text(doc, "В «Редакторе пар» можно отфильтровать поток по группе и типу занятий, изменить тип и пометить поток как исключённый. Исключённые потоки не должны участвовать в последующем расчёте.")
    add_heading(doc, "3.3 Справочники и доступность", 2)
    add_text(doc, "В «Справочниках» ведутся корпуса, аудитории, оснащение, типы занятий, дисциплины, профили правил, преподаватели и группы. Для аудитории указываются тип, вместимость, активность и оснащение. Неактивная аудитория не может использоваться как ресурс в корректном расписании.")
    add_text(doc, "Правило доступности задаётся для преподавателя, группы, аудитории или глобально. Оно может быть еженедельным, для конкретной даты или диапазона дат. Режимы: недоступно, доступно, предпочтительно; правило может быть жёстким либо иметь вес 1–10.")
    add_heading(doc, "4. Планирование и расчёт")
    add_heading(doc, "4.1 Календарь и недельная нагрузка", 2)
    add_text(doc, "Создайте учебный период с датой начала и окончания. Система хранит планирование по неделям: для каждого потока задаётся количество занятий и приоритет. Это позволяет корректно учитывать неравномерную нагрузку в семестре.")
    add_note(doc, "Ограничение расчёта", "Один запуск ограничен горизонтом в 14 календарных дней. Семестр формируется последовательностью недельных задач; не пытайтесь рассчитывать весь семестр как один длительный запуск.")
    add_heading(doc, "4.2 Запуск расчёта", 2)
    add_numbers(doc, [
        "Откройте раздел «Расчёты» и выберите подготовленный период/недели.",
        "Уточните активные типы занятий, приоритеты дисциплин и праздники.",
        "Запустите расчёт и наблюдайте прогресс выполнения. Параллельный запуск в пересекающейся области система не допускает.",
        "После завершения перейдите в «Расписание» либо «Журнал операций» для анализа версии и её диагностики.",
    ])
    add_heading(doc, "5. Проверка, редактирование и публикация")
    add_heading(doc, "5.1 Проверка результата", 2)
    add_text(doc, "В «Расписании» выберите расчёт, группу и неделю. Сетка показывает пары и занятия. Карточки содержат дисциплину, тип занятия, преподавателя, аудиторию и предупреждения. Список конфликтов показывает записи, требующие внимания.")
    add_heading(doc, "5.2 Ручная корректировка", 2)
    add_text(doc, "При изменении даты, номера пары, преподавателя или аудитории сервер проверяет пересечение группы, преподавателя и аудитории; доступность; активность аудитории; а также принадлежность даты периоду версии. При нарушении правка отклоняется с перечнем причин. Если занятие нельзя сдвигать при следующей генерации, включите его фиксацию.")
    add_heading(doc, "5.3 Версии и публикация", 2)
    add_bullets(doc, [
        "Черновик — результат расчёта и ручной корректировки. Его можно проверять, отменять или повторно запускать.",
        "Публикация делает версию действующей; предыдущая опубликованная версия того же периода архивируется.",
        "Опубликованная версия доступна только для чтения. Экспорт без выбора задачи выгружает опубликованную версию.",
        "Каждая ручная правка увеличивает редакцию версии, поэтому экспорт соответствует конкретному состоянию расписания.",
    ])
    add_heading(doc, "5.4 Выгрузка", 2)
    add_text(doc, "Экспорт формирует Excel-файл. Он включает лист с исходными строками и лист «Расписание» с сеткой по датам, парам и группам. Предупреждения и типы занятий визуально выделяются, что удобно для согласования.")
    add_heading(doc, "6. Частые ситуации")
    add_table(doc, ["Ситуация", "Действие оператора"], [
        ("Расчёт не запускается (конфликт 409)", "Дождитесь завершения, отмены или ошибки пересекающегося расчёта. Повторный запуск разблокируется автоматически после завершения жизненного цикла задачи."),
        ("Занятие нельзя перенести", "Проверьте сообщение системы: обычно конфликтует группа, преподаватель, аудитория, правило доступности либо дата вне периода."),
        ("В результате нет аудитории", "Проверьте вместимость, активность, тип аудитории и требуемое оснащение. Скорректируйте справочник или настройку потока, затем запустите новый расчёт."),
        ("Нужно остановить долгий расчёт", "Откройте «Журнал операций» и отмените задачу. После отмены можно скорректировать условия и выполнить повторный запуск."),
        ("Нужна корректировка уже опубликованного расписания", "Не изменяйте опубликованную версию напрямую. Создайте/повторите расчёт как новую версию, внесите правки, согласуйте и опубликуйте её."),
    ], [2800, 6560], 9)
    path = OUTPUT / "02_Руководство_пользователя.docx"
    doc.save(path)
    return path


def build_developer_document() -> Path:
    doc = Document()
    configure_document(doc, "Руководство разработчика и развёртывания", "Техническая эксплуатация системы")
    add_contents(doc, [
        "1. Архитектура", "2. Состав репозитория", "3. Требования и конфигурация",
        "4. Развёртывание Docker Compose", "5. Локальная разработка", "6. База данных и миграции",
        "7. API и фоновые задачи", "8. Проверка, мониторинг и резервное копирование",
    ])
    add_heading(doc, "1. Архитектура")
    add_text(doc, "Система построена как web-приложение: React SPA обслуживается Nginx, обращается к FastAPI по HTTP API; API хранит данные в PostgreSQL, отправляет длительные расчёты в Celery, а Redis используется как брокер и backend задач. Планировщик использует Google OR-Tools CP-SAT.")
    add_table(doc, ["Компонент", "Технологии", "Функция"], [
        ("Frontend", "React 19, TypeScript, Vite, Zustand, TailwindCSS", "Операторский интерфейс: импорт, справочники, календарь, расчёты, сетка и журнал."),
        ("Backend", "FastAPI, Pydantic v2, SQLAlchemy 2.0 async", "REST API, бизнес-правила, валидация конфликтов, экспорт Excel."),
        ("Database", "PostgreSQL 17", "Транзакционное хранение справочников, расчётов, версий и расписания."),
        ("Worker", "Celery 5, Redis 8", "Асинхронный запуск и контроль ресурсоёмких задач генерации."),
        ("Optimizer", "Google OR-Tools", "Построение и решение модели расписания с ограничениями и приоритетами."),
    ], [1900, 3000, 4460], 9)
    add_heading(doc, "2. Состав репозитория")
    add_table(doc, ["Путь", "Содержимое"], [
        ("src/app/api/routes", "FastAPI endpoints: scheduler, planning, reference."),
        ("src/app/services", "Бизнес-логика импорта, генерации, жизненного цикла, проверки качества, экспорта."),
        ("src/app/database", "SQLAlchemy-модели и асинхронная сессия БД."),
        ("src/app/migrations", "Alembic-конфигурация и версии миграций."),
        ("src/app/tests", "Тесты здоровья, планирования, справочников, генерации и lifecycle."),
        ("spa/src/pages", "Страницы интерфейса оператора."),
        ("spa/src/store", "Общее состояние интерфейса на Zustand."),
        ("docker-compose.yml", "Production-подобная композиция сервисов."),
    ], [3000, 6360], 9)
    add_heading(doc, "3. Требования и конфигурация")
    add_text(doc, "Для контейнерного запуска необходимы Docker Engine с Docker Compose. Для локальной разработки: Python 3.10+, Node.js, PostgreSQL и Redis. Производственная БД — PostgreSQL; пароль и секреты не должны храниться в Git.")
    add_table(doc, ["Переменная", "Назначение", "Примечание"], [
        ("POSTGRES_USER", "Пользователь PostgreSQL", "Обязательна для Compose."),
        ("POSTGRES_PASSWORD", "Пароль PostgreSQL", "Используйте уникальный секрет production."),
        ("POSTGRES_DATABASE", "Имя БД", "Используется сервисами backend и worker."),
        ("POSTGRES_PORT", "Внешний порт PostgreSQL", "По умолчанию в Compose: 5446."),
        ("SECRET_KEY", "Подпись токенов", "Длинное случайное значение; не публиковать."),
        ("CORS_ORIGINS", "Разрешённые источники браузера", "Список через запятую; задайте домен production."),
        ("CELERY_WORKER_CONCURRENCY", "Параллелизм worker", "Подбирается по CPU/RAM сервера."),
        ("DATABASE_URL / REDIS_URL", "Подключения приложения", "В Compose формируются для внутренних имён сервисов."),
        ("VITE_API_BASE_URL", "Префикс API SPA", "Задаётся при сборке frontend."),
    ], [2600, 3150, 3610], 8.5)
    add_heading(doc, "4. Развёртывание Docker Compose")
    add_numbers(doc, [
        "Скопируйте .env.example в .env и замените значения POSTGRES_PASSWORD и SECRET_KEY на безопасные. Проверьте CORS_ORIGINS для внешнего домена.",
        "Соберите и запустите сервисы командой: docker compose --env-file .env up -d --build.",
        "Проверьте состояние: docker compose ps. Backend готов, когда отвечает /health/live и /health/ready; Compose ожидает readiness БД перед запуском API.",
        "Откройте frontend на опубликованном порту 80. API доступен через frontend/Nginx либо напрямую на порту 8000, если он не закрыт сетевыми правилами.",
        "При первом запуске backend применяет миграции, потому что RUN_MIGRATIONS=true. Worker запускается после готовности backend и не выполняет миграции.",
    ])
    add_table(doc, ["Сервис", "Порт/том", "Назначение"], [
        ("postgres", "${POSTGRES_PORT}:5432; postgres_data", "Персистентная PostgreSQL 17."),
        ("redis", "redis_data", "Очередь и результат Celery; AOF включён."),
        ("backend", "8000:8000; uploads, backend_logs", "FastAPI и автоматическое применение миграций."),
        ("worker", "uploads, backend_logs", "Celery worker, concurrency configurable."),
        ("frontend", "80:80", "Сборка SPA и reverse proxy."),
    ], [2200, 3100, 4060], 9)
    add_note(doc, "Production", "Разрешите наружу только необходимые порты, завершайте TLS на reverse proxy/балансировщике, используйте отдельные секреты, ограничьте доступ к PostgreSQL и регулярно проверяйте журналы backend/worker.")
    add_heading(doc, "5. Локальная разработка")
    add_text(doc, "Backend запускается из каталога src. Перед началом создайте виртуальное окружение, установите зависимости из requirements.txt и настройте переменные окружения. SPA запускается из каталога spa после установки зависимостей npm.")
    add_table(doc, ["Действие", "Команда"], [
        ("Установить backend-зависимости", "cd src && python -m pip install -r requirements.txt"),
        ("Применить миграции", "cd src && alembic upgrade head"),
        ("Запустить API", "cd src && uvicorn main:app --app-dir app --reload"),
        ("Установить SPA-зависимости", "cd spa && npm install"),
        ("Запустить SPA", "cd spa && npm run dev"),
        ("Запустить worker", "cd src && celery --app=worker.celery_app worker --loglevel=INFO"),
    ], [3200, 6160], 9)
    add_heading(doc, "6. База данных и миграции")
    add_bullets(doc, [
        "Миграции находятся в src/app/migrations/versions. Создавайте их из каталога src: alembic revision --autogenerate -m \"описание\".",
        "Перед production-миграцией создайте и проверьте резервную копию PostgreSQL; затем примените alembic upgrade head.",
        "Не используйте AUTO_CREATE_TABLES как механизм production-эволюции схемы. Эволюция выполняется только миграциями Alembic.",
        "После изменения модели проверьте alembic check и сценарии чтения/записи, затронутые миграцией.",
    ])
    add_heading(doc, "7. API и фоновые задачи")
    add_text(doc, "Все маршруты прикладного API размещены под /api/v1. Подмаршруты: /scheduler — импорт, генерация, версии, запись расписания и экспорт; /planning — периоды, недели и нагрузка; /reference — справочники, доступность и профили правил.")
    add_table(doc, ["Группа", "Примеры операций"], [
        ("Импорт и данные", "POST /scheduler/import/streams; GET /scheduler/import/history; PATCH /scheduler/streams/{id}."),
        ("Генерация", "POST /scheduler/generate; GET /scheduler/tasks; POST cancel/retry/publish/archive; diagnostics/components."),
        ("Расписание", "GET /scheduler/schedule; PATCH/DELETE /scheduler/schedule/{entry_id}; GET /scheduler/export."),
        ("Планирование", "Создание периода, список недель, распределение и замена недельной нагрузки."),
        ("Справочники", "CRUD для аудиторий и справочных сущностей, доступности, профилей правил; обновление преподавателя, группы и требований потока."),
    ], [2300, 7060], 9)
    add_text(doc, "Длительный расчёт создаёт GenerationTask и обрабатывается worker. Блокировки области расчёта не позволяют одновременно запускать пересекающиеся задачи. При отмене отзываются задачи Celery; при потере worker задача переводится в failed, сохраняется диагностика, а блокировки освобождаются.")
    add_heading(doc, "8. Проверка, мониторинг и резервное копирование")
    add_table(doc, ["Проверка", "Команда / критерий"], [
        ("Backend-стиль", "ruff check src/app"),
        ("Backend-тесты", "python -m pytest"),
        ("Frontend", "cd spa && npm run build"),
        ("Схема", "cd src && alembic upgrade head && alembic check"),
        ("Compose", "docker compose --env-file .env.example config --quiet"),
        ("Здоровье", "GET /health/live — процесс; GET /health/ready — соединение с БД."),
        ("Резервная копия", "Регулярный pg_dump БД; отдельно сохранять том uploads и, при необходимости, backend_logs."),
    ], [2700, 6660], 9)
    add_note(doc, "Приёмка обновления", "После развёртывания проверьте параллельный запуск, отмену расчёта, повторный запуск, конфликтное перемещение записи, фиксацию занятия, публикацию новой версии и Excel-экспорт опубликованного расписания.")
    path = OUTPUT / "03_Руководство_разработчика_и_развертывания.docx"
    doc.save(path)
    return path


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for builder in (build_database_document, build_user_document, build_developer_document):
        print(builder())


if __name__ == "__main__":
    main()
