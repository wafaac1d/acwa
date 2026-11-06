from acwa.config import THREADS_TEXT_LIMIT
from acwa.content.length import contains_emoji, contains_hashtag, contains_link, threads_length


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


def _forbidden_phrases(forbidden: str) -> list[str]:
    phrases: list[str] = []
    for line in forbidden.splitlines():
        phrase = line.strip()
        if len(phrase) >= 3:
            phrases.append(phrase)
    return phrases
