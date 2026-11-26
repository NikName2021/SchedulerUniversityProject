from services.parser_service import parse_streams_content


def test_csv_import_keeps_same_subject_for_different_teachers_separate() -> None:
    csv_content = """Мероприятие;Вид потока;Преподаватель;Группа;Кол-во пар
Математика;Л;Иванов И.И.;ГР-1 [20];2
Математика;Л;Петров П.П.;ГР-2 [18];2
""".encode()

    streams = parse_streams_content(csv_content, "streams.csv")

    assert len(streams) == 2
    assert {stream["teacher"] for stream in streams} == {
        "Иванов И.И.",
        "Петров П.П.",
    }


def test_duplicate_group_uses_largest_reported_size() -> None:
    csv_content = """Мероприятие;Вид потока;Преподаватель;Группа
Физика;П;Иванов И.И.;ФИЗ-101 [18]
Физика;П;Иванов И.И.;ФИЗ-101 [24]
""".encode()

    streams = parse_streams_content(csv_content, "streams.csv")

    assert streams[0]["groups"] == [{"name": "ФИЗ-101", "size": 24}]


def test_joint_language_group_keeps_a_single_audience_label() -> None:
    csv_content = """Мероприятие;Вид потока;Преподаватель;Группа
Английский язык;П;Иванов И.И.;К0109-23 [10], К0609-23 [12] (L2)
""".encode()

    streams = parse_streams_content(csv_content, "streams.csv")

    assert streams[0]["groups"] == [{"name": "К0109-23, К0609-23 (L2)", "size": 22}]


def test_excel_flow_column_keeps_separate_streams_and_subgroups() -> None:
    csv_content = """Поток;Мероприятие;Вид потока;Преподаватель;Группа;Нагрузка
К0409-26/1;История;С;Иванов И.И.;К0409-26/1 [21];18
К0409-26/2;История;С;Иванов И.И.;К0409-26/2 [18];18
К0409-26/1 (L1);Иностранный язык;С;Петров П.П.;К0409-26/1 [11];24
К0409-26/1 (L2);Иностранный язык;С;Петров П.П.;К0409-26/1 [10];24
К1609-25/1 (a);Второй язык;С;Сидоров С.С.;К1609-25/1 [12];18
К1609-25/1 (b);Второй язык;С;Сидоров С.С.;К1609-25/1 [13];18
""".encode()

    streams = parse_streams_content(csv_content, "streams.csv")

    assert len(streams) == 6
    assert {stream["type"] for stream in streams} == {"Семинар"}
    assert [stream["groups"] for stream in streams] == [
        [{"name": "К0409-26/1", "size": 21}],
        [{"name": "К0409-26/2", "size": 18}],
        [{"name": "К0409-26/1 (L1)", "size": 11}],
        [{"name": "К0409-26/1 (L2)", "size": 10}],
        [{"name": "К1609-25/1 (L1)", "size": 12}],
        [{"name": "К1609-25/1 (L2)", "size": 13}],
    ]


def test_language_stream_preserves_three_subgroups_and_their_member_groups() -> None:
    csv = """Поток;Мероприятие;Вид потока;Преподаватель;Группа
К0409-26(A);Иностранный язык;П;Первый;К0409-26/1 [4]К0409-26/2 [6]
К0409-26(В);Иностранный язык;П;Второй;К0409-26/1 [3]К0409-26/2 [5]
К0409-26(С);Иностранный язык;П;Третий;К0409-26/1 [2]К0409-26/2 [4]
"""

    streams = parse_streams_content(csv.encode(), "streams.csv")

    assert [stream["groups"] for stream in streams] == [
        [{"name": "К0409-26/1, К0409-26/2 (L1)", "size": 10}],
        [{"name": "К0409-26/1, К0409-26/2 (L2)", "size": 8}],
        [{"name": "К0409-26/1, К0409-26/2 (L3)", "size": 6}],
    ]


def test_slash_separated_language_subgroups_map_to_three_parallel_subgroups() -> None:
    csv = """Поток;Мероприятие;Вид потока;Преподаватель;Группа
ИОП-ИТ-25/А;Иностранный язык;П;Гаранян А.В.;ИОП-ИТ-25/1 [5]ИОП-ИТ-25/2 [6]
ИОП-ИТ-25/B;Иностранный язык;П;Карагозян Л.Д.;ИОП-ИТ-25/1 [10]ИОП-ИТ-25/2 [5]
ИОП-ИТ-25/C;Иностранный язык;П;Половникова Н.А.;ИОП-ИТ-25/1 [7]ИОП-ИТ-25/2 [12]
"""

    streams = parse_streams_content(csv.encode(), "streams.csv")

    assert [stream["groups"] for stream in streams] == [
        [{"name": "ИОП-ИТ-25/1, ИОП-ИТ-25/2 (L1)", "size": 11}],
        [{"name": "ИОП-ИТ-25/1, ИОП-ИТ-25/2 (L2)", "size": 15}],
        [{"name": "ИОП-ИТ-25/1, ИОП-ИТ-25/2 (L3)", "size": 19}],
    ]


def test_assessment_stream_types_do_not_fall_back_to_extracurricular() -> None:
    csv = """Поток;Мероприятие;Вид потока;Преподаватель;Группа
ИОП-ИТ-25/1;Математика;ЗД;Кузнецов С.Б.;ИОП-ИТ-25/1 [22]
ИОП-ИТ-25/1;Математика;ПА;;ИОП-ИТ-25/1 [22]
ИОП-ИТ-25/1;Дискретная математика;Э;Кручинин Д.В.;ИОП-ИТ-25/1 [22]
Внеучебная деятельность;Защита проектов;Внеучебное мероприятие;Семенов М.Е.;ИОП-ИТ-25/1 [22]
"""

    streams = parse_streams_content(csv.encode(), "streams.csv")

    assert [stream["type"] for stream in streams] == [
        "Зачет",
        "Зачет",
        "Зачет",
        "Внеучебное мероприятие",
    ]
