from datetime import date
from uuid import UUID

from acwa.scheduling.calc import parse_hhmm, validate_timezone

MAX_TIMES = 12


def campaign_field_errors(data: dict[str, object]) -> dict[str, str]:
    errors: dict[str, str] = {}
    name = _text(data.get("name"))
    topic = _text(data.get("topic"))
    if not name:
        errors["name"] = "Укажите название кампании"
    elif len(name) > 120:
        errors["name"] = "Название не длиннее 120 символов"
    if not topic:
        errors["topic"] = "Укажите тему публикаций"
    elif len(topic) > 300:
        errors["topic"] = "Тема не длиннее 300 символов"
    _limit(errors, data, "context", 4000, "Контекст")
    _limit(errors, data, "audience", 300, "Аудитория")
    _limit(errors, data, "tone", 200, "Тон")
    _limit(errors, data, "goal", 300, "Цель")
    _limit(errors, data, "extra_instructions", 2000, "Инструкции")
    _limit(errors, data, "required_points", 2000, "Тезисы")
    _limit(errors, data, "forbidden", 2000, "Ограничения")
    _limit(errors, data, "examples", 4000, "Примеры")
    language = _text(data.get("language")) or "ru"
    if len(language) < 2 or len(language) > 16:
        errors["language"] = "Укажите язык, например ru"
    if data.get("desired_length") not in {"short", "medium", "long"}:
        errors["desired_length"] = "Выберите короткую, среднюю или длинную подачу"
    if data.get("publish_mode") not in {"manual", "automatic"}:
        errors["publish_mode"] = "Выберите ручное подтверждение или автоматическую публикацию"
    timezone = _text(data.get("timezone"))
    if not timezone:
        errors["timezone"] = "Укажите часовой пояс IANA, например Europe/Moscow"
    else:
        try:
            validate_timezone(timezone)
        except ValueError:
            errors["timezone"] = "Неизвестный часовой пояс. Нужен идентификатор IANA, не смещение UTC"
    weekdays = data.get("weekdays")
    if not isinstance(weekdays, list) or not weekdays:
        errors["weekdays"] = "Выберите хотя бы один день недели"
    elif any(not isinstance(day, int) or day < 1 or day > 7 for day in weekdays):
        errors["weekdays"] = "Дни недели задаются числами от 1 (понедельник) до 7 (воскресенье)"
    elif len(set(weekdays)) != len(weekdays):
        errors["weekdays"] = "Дни недели не должны повторяться"
    times = data.get("times_of_day")
    if not isinstance(times, list) or not times:
        errors["times_of_day"] = "Добавьте хотя бы одно время публикации"
    elif len(times) > MAX_TIMES:
        errors["times_of_day"] = f"Не больше {MAX_TIMES} времён в день"
    elif len(set(times)) != len(times):
        errors["times_of_day"] = "Время публикации не должно повторяться"
    else:
        for value in times:
            if not isinstance(value, str):
                errors["times_of_day"] = "Время указывается строкой ЧЧ:ММ"
                break
            try:
                parse_hhmm(value)
            except ValueError:
                errors["times_of_day"] = f"Некорректное время: {value}. Используйте ЧЧ:ММ"
                break
    starts_on = data.get("starts_on")
    ends_on = data.get("ends_on")
    if not isinstance(starts_on, date):
        errors["starts_on"] = "Укажите дату начала"
    elif isinstance(ends_on, date) and ends_on < starts_on:
        errors["ends_on"] = "Дата окончания не может быть раньше даты начала"
    account_id = data.get("account_id")
    if not isinstance(account_id, UUID):
        errors["account_id"] = "Выберите подключённый аккаунт"
    return errors


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _limit(errors: dict[str, str], data: dict[str, object], field: str, limit: int, label: str) -> None:
    value = data.get(field, "")
    if value is None:
        return
    if not isinstance(value, str):
        errors[field] = f"{label}: ожидается текст"
        return
    if len(value) > limit:
        errors[field] = f"{label} не длиннее {limit} символов"
