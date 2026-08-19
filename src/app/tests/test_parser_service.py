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

    assert streams[0]["groups"] == [
        {"name": "К0109-23, К0609-23 (L2)", "size": 22}
    ]
