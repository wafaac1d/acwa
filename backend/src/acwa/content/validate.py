from acwa.config import THREADS_TEXT_LIMIT
from acwa.content.length import contains_emoji, contains_hashtag, contains_link, threads_length

TOPIC_TAG_LIMIT = 50


def validate_post_text(
    text: str,
    *,
    allow_emoji: bool,
    allow_hashtags: bool,
    allow_links: bool,
    forbidden: str,
) -> list[str]:
    errors: list[str] = []
    cleaned = text.strip()
    if not cleaned:
        return ["Текст поста пустой"]
    units = threads_length(cleaned)
    if units > THREADS_TEXT_LIMIT:
        errors.append(
            f"Текст длиннее лимита Threads: {units} при максимуме {THREADS_TEXT_LIMIT}. "
            "Желаемая длина кампании — только пожелание."
        )
    if not allow_emoji and contains_emoji(cleaned):
        errors.append("В тексте есть эмодзи, а кампания их запрещает")
    if not allow_hashtags and contains_hashtag(cleaned):
        errors.append("В тексте есть хэштег, а кампания их запрещает")
    if not allow_links and contains_link(cleaned):
        errors.append("В тексте есть ссылка, а кампания их запрещает")
    for phrase in _forbidden_phrases(forbidden):
        if phrase.casefold() in cleaned.casefold():
            errors.append(f"Текст содержит запрещённое выражение: {phrase}")
    return errors


def normalize_reply_text(
    value: object,
    *,
    allow_emoji: bool,
    allow_hashtags: bool,
    allow_links: bool,
    forbidden: str,
) -> tuple[str | None, str | None]:
    """Return a continuation comment or the first Threads validation error. Blank means none."""
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "Продолжение в комментарии должно быть текстом"
    cleaned = value.strip()
    if not cleaned:
        return None, None
    errors = validate_post_text(
        cleaned,
        allow_emoji=allow_emoji,
        allow_hashtags=allow_hashtags,
        allow_links=allow_links,
        forbidden=forbidden,
    )
    if errors:
        return None, errors[0]
    return cleaned, None


def normalize_topic_tag(value: object) -> tuple[str | None, str | None]:
    """Return a Threads topic_tag or an error. Blank means no tag.

    Official limits: 1–50 characters, periods and ampersands are rejected.
    A leading # is stripped because the parameter is the tag text, not a hashtag.
    """
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "Тема Threads должна быть текстом"
    cleaned = value.strip().removeprefix("#").strip()
    if not cleaned:
        return None, None
    if len(cleaned) > TOPIC_TAG_LIMIT:
        return None, f"Тема Threads не длиннее {TOPIC_TAG_LIMIT} символов"
    if any(char in cleaned for char in ".&\n\r\t"):
        return None, "В теме Threads нельзя использовать точку, амперсанд и переносы строки"
    return cleaned, None


def _forbidden_phrases(forbidden: str) -> list[str]:
    phrases: list[str] = []
    for line in forbidden.splitlines():
        phrase = line.strip()
        if len(phrase) >= 3:
            phrases.append(phrase)
    return phrases
