import re

_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)(access_token=)[^&\s\"']+"),
    re.compile(r"(?i)(client_secret=)[^&\s\"']+"),
    re.compile(r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9\-._]+"),
    re.compile(r"(?i)(\"token_ciphertext\"\s*:\s*\")[^\"]+"),
)


def redact(value: str) -> str:
    redacted = value
    for pattern in _PATTERNS:
        redacted = pattern.sub(r"\1[redacted]", redacted)
    return redacted
