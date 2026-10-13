from __future__ import annotations

from typing import Any

from core.config import (
    DEFAULT_COMPONENT_TIME_SECONDS,
    PLACEMENT_STAGE_TIME_RATIO,
    WINDOW_STAGE_TIME_RATIO,
)
from core.constants import ROOM_ASSIGNMENT_ENABLED, ROOM_FUND_ENABLED

RULE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "code": "double_booking",
        "name": "Без пересечений",
        "description": (
            "Группа, подгруппа или преподаватель не могут участвовать в двух "
            "занятиях одновременно. Общий поток занимает время у всех входящих групп."
        ),
        "category": "Конфликты",
        "configurable": False,
        "default_is_hard": True,
        "default_weight": 10,
        "system_note": "Системное ограничение — отключение пока недоступно.",
    },
    {
        "code": "unavailable_time",
        "name": "Учет недоступного времени",
        "description": (
            "Генератор исключает запрещенные даты и пары для преподавателей, "
            "групп и университета."
        ),
        "category": "Доступность",
        "configurable": False,
        "default_is_hard": True,
        "default_weight": 10,
        "system_note": "Системное ограничение — отключение пока недоступно.",
    },
    {
        "code": "locked_events",
        "name": "Сохранение закрепленных занятий",
        "description": (
            "Уже закрепленные занятия сохраняют дату и номер пары при повторном "
            "расчете расписания."
        ),
        "category": "Закрепленные занятия",
        "configurable": False,
        "default_is_hard": True,
        "default_weight": 10,
        "system_note": "Системное ограничение — отключение пока недоступно.",
    },
    {
        "code": "room_capacity",
        "name": "Вместимость аудитории",
        "description": (
            "Предпочитает аудиторию, в которую помещаются все участники занятия."
        ),
        "category": "Аудитории",
        "configurable": True,
        "requires_rooms": True,
    },
    {
        "code": "room_type",
        "name": "Тип аудитории",
        "description": (
            "Сопоставляет лекции, семинары и лабораторные с подходящим типом аудитории."
        ),
        "category": "Аудитории",
        "configurable": True,
        "requires_rooms": True,
    },
    {
        "code": "room_features",
        "name": "Оснащение аудитории",
        "description": (
            "Проверяет наличие требуемого оборудования и особенностей аудитории."
        ),
        "category": "Аудитории",
        "configurable": True,
        "requires_rooms": True,
        "default_weight": 7,
    },
    {
        "code": "minimize_windows",
        "name": "Минимизация окон",
        "description": (
            "Штрафует свободные пары между первым и последним занятием группы за день."
        ),
        "category": "Качество расписания",
        "configurable": True,
    },
    {
        "code": "lunch_break",
        "name": "Перерыв на обед",
        "description": (
            "Оставляет группе свободной третью или четвертую пару, чтобы в середине "
            "дня был перерыв."
        ),
        "category": "Качество расписания",
        "configurable": True,
        "default_is_hard": True,
    },
    {
        "code": "lecture_before_practice",
        "name": "Лекция перед практикой",
        "description": (
            "Старается не опережать лекционный материал семинарами и лабораторными "
            "по той же дисциплине."
        ),
        "category": "Последовательность занятий",
        "configurable": True,
    },
    {
        "code": "late_lessons",
        "name": "Меньше поздних пар",
        "description": (
            "Предпочитает более ранние пары. Для групп с большой нагрузкой этот "
            "приоритет усиливается."
        ),
        "category": "Качество расписания",
        "configurable": True,
    },
    {
        "code": "teacher_preferences",
        "name": "Пожелания преподавателей",
        "description": (
            "Учитывает предпочтительные и нежелательные интервалы преподавателей."
        ),
        "category": "Доступность",
        "configurable": True,
    },
    {
        "code": "load_balance",
        "name": "Равномерность нагрузки",
        "description": (
            "Предназначено для равномерного распределения занятий группы по дням недели."
        ),
        "category": "Качество расписания",
        "configurable": True,
        "implemented": False,
    },
)


def describe_solver_timing() -> dict[str, Any]:
    """Return the nominal lexicographic stage limits shown in rule profiles."""
    total_seconds = float(DEFAULT_COMPONENT_TIME_SECONDS)
    placement_seconds = round(total_seconds * PLACEMENT_STAGE_TIME_RATIO, 2)
    window_seconds = round(total_seconds * WINDOW_STAGE_TIME_RATIO, 2)
    quality_seconds = round(
        max(0.0, total_seconds - placement_seconds - window_seconds), 2
    )
    return {
        "total_component_seconds": total_seconds,
        "scope": "На каждую независимую группу конфликтующих занятий",
        "stages": [
            {
                "code": "placement",
                "name": "Размещение занятий",
                "seconds": placement_seconds,
                "allocation": "maximum",
                "description": (
                    f"До {PLACEMENT_STAGE_TIME_RATIO:.0%} общего бюджета на "
                    "минимизацию неразмещённых занятий."
                ),
            },
            {
                "code": "windows",
                "name": "Минимизация окон",
                "seconds": window_seconds,
                "allocation": "maximum",
                "description": (
                    f"До {WINDOW_STAGE_TIME_RATIO:.0%} общего бюджета после "
                    "фиксации результата размещения."
                ),
            },
            {
                "code": "quality",
                "name": "Остальные критерии качества",
                "seconds": quality_seconds,
                "allocation": "remainder",
                "description": "Получает всё время, оставшееся после первых двух этапов.",
            },
        ],
        "note": (
            "Первые два значения — верхние лимиты. Этап качества получает "
            "фактический остаток: он будет больше 120 секунд, если предыдущие "
            "этапы завершатся раньше, и меньше — если подготовка модели или поиск "
            "займут больше времени."
        ),
    }


def describe_rule_profile(settings: list[Any]) -> list[dict[str, Any]]:
    """Combine stored profile values with the generator's actual capabilities."""
    settings_by_code = {item.rule_code: item for item in settings}
    descriptions: list[dict[str, Any]] = []

    for definition in RULE_CATALOG:
        code = definition["code"]
        setting = settings_by_code.pop(code, None)
        configured_enabled = bool(setting.enabled) if setting is not None else True
        is_hard = (
            bool(setting.is_hard)
            if setting is not None
            else bool(definition.get("default_is_hard", False))
        )
        weight = (
            int(setting.weight)
            if setting is not None
            else int(definition.get("default_weight", 5))
        )
        note = definition.get("system_note")

        if not definition.get("implemented", True):
            runtime_state = "not_implemented"
            effective_enabled = False
            note = "Правило подготовлено в профиле, но пока не подключено к генератору."
        elif definition.get("requires_rooms") and (
            not ROOM_ASSIGNMENT_ENABLED or not ROOM_FUND_ENABLED
        ):
            runtime_state = "temporarily_disabled"
            effective_enabled = False
            note = "Временно не применяется: выставление аудиторий и фонд отключены."
        elif not definition.get("configurable", True):
            runtime_state = "active"
            effective_enabled = True
        elif configured_enabled:
            runtime_state = "active"
            effective_enabled = True
        else:
            runtime_state = "disabled"
            effective_enabled = False

        descriptions.append(
            {
                "code": code,
                "name": definition["name"],
                "description": definition["description"],
                "category": definition["category"],
                "configured_enabled": configured_enabled,
                "effective_enabled": effective_enabled,
                "is_hard": is_hard,
                "weight": weight,
                "configurable": bool(definition.get("configurable", True)),
                "runtime_state": runtime_state,
                "runtime_note": note,
            }
        )

    for code, setting in sorted(settings_by_code.items()):
        descriptions.append(
            {
                "code": code,
                "name": code,
                "description": "Для этого правила пока не добавлено описание.",
                "category": "Прочее",
                "configured_enabled": bool(setting.enabled),
                "effective_enabled": False,
                "is_hard": bool(setting.is_hard),
                "weight": int(setting.weight),
                "configurable": True,
                "runtime_state": "not_implemented",
                "runtime_note": "Правило отсутствует в текущей версии генератора.",
            }
        )

    return descriptions
