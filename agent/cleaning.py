"""Input cleaning and prompt-injection screening. Runs before any model sees an email."""
import re
import unicodedata

MAX_FIELD_CHARS = 8000
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿‪‫‬‭‮"))
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION_PATTERNS = {
    "override_instructions": r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instruction|prompt|rule|system)s?\b",
    "role_hijack": r"\b(you are now|act as|pretend to be|new role|developer mode|jailbreak)\b",
    "reveal_prompt": r"\b(reveal|show|print|repeat)\b.{0,30}\b(system prompt|instructions|api key|secret)\b",
    "force_decision": r"\b(approve|credit|accept|mark)\b.{0,30}\b(this claim|all claims|as valid|immediately)\b.{0,30}(without|regardless|no need)",
    "chat_markup": r"(<\|?(system|assistant|im_start)\|?>|\[/?INST\]|^\s*(system|assistant)\s*:)",
}


def clean_text(value: object) -> str:
    """Normalise unicode, drop invisible/control characters and cap length. Keeps newlines."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_INVISIBLE)
    text = _CONTROL.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_FIELD_CHARS]


def scan_for_injection(text: str) -> list[str]:
    """Names of the injection patterns found in the text (empty when it looks clean)."""
    return [
        name for name, pattern in _INJECTION_PATTERNS.items()
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    ]


def sanitize_email(email: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Return a cleaned copy of the email and any injection patterns found in subject or body."""
    cleaned = {key: clean_text(value) for key, value in email.items()}
    flags = scan_for_injection(cleaned.get("subject", "") + "\n" + cleaned.get("body", ""))
    return cleaned, flags
