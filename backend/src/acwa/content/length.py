import regex

_EMOJI = regex.compile(r"\p{Extended_Pictographic}")
_HASHTAG = regex.compile(r"(?<!\w)#\w+", regex.UNICODE)
_LINK = regex.compile(r"(https?://|www\.)", regex.IGNORECASE)


def threads_length(text: str) -> int:
    """Count Threads text units.

    Meta documents a 500-character limit and states that emoji are counted as
    their UTF-8 byte length. Other grapheme clusters count as one unit.
    """
    total = 0
    for grapheme in regex.findall(r"\X", text):
        if _EMOJI.search(grapheme):
            total += len(grapheme.encode("utf-8"))
        else:
            total += 1
    return total


def contains_hashtag(text: str) -> bool:
    return _HASHTAG.search(text) is not None


def contains_link(text: str) -> bool:
    return _LINK.search(text) is not None


def contains_emoji(text: str) -> bool:
    return _EMOJI.search(text) is not None
