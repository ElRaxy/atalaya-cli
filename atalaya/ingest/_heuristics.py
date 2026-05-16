"""Heurísticas compartidas entre parsers de email (stack, seniority, location)."""

from __future__ import annotations

import re
from typing import Final

_STACK_KEYWORDS: Final = (
    "react",
    "node",
    "nodejs",
    "node.js",
    "python",
    "typescript",
    "javascript",
    "vue",
    "angular",
    "ruby",
    "rails",
    "go",
    "golang",
    "java",
    "spring",
    "php",
    "laravel",
    "rust",
    "kotlin",
    "swift",
    "flutter",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "postgres",
    "postgresql",
    "mongo",
    "mongodb",
    "redis",
    "graphql",
    "nextjs",
    "next.js",
    "nestjs",
    "express",
    "django",
    "fastapi",
    "ai",
    "ml",
    "llm",
    ".net",
    "c#",
)

_SENIORITY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "intern": ("intern", "trainee", "becario", "prácticas", "practicas"),
    "junior": ("junior", "jr.", "entry-level", "entry level"),
    "senior": ("senior", "sr.", "staff", "principal", "lead"),
    "mid": ("mid-level", "mid level", "mid-senior", "ssr.", " mid "),
}

_REMOTE_HINTS: Final = (
    "remote",
    "remoto",
    "teletrabajo",
    "100% remote",
    "fully remote",
    "work from home",
    "home office",
)


def detect_stack(text: str) -> list[str]:
    """Extrae tecnologías mencionadas. Match con word-boundary."""
    if not text:
        return []
    found: list[str] = []
    haystack = text.lower()
    for kw in _STACK_KEYWORDS:
        pattern = r"(?<![a-z0-9+#.])" + re.escape(kw) + r"(?![a-z0-9+#])"
        if re.search(pattern, haystack):
            canonical = (
                kw.replace("node.js", "node")
                .replace("nodejs", "node")
                .replace("next.js", "nextjs")
                .replace("postgresql", "postgres")
                .replace("mongodb", "mongo")
                .replace("golang", "go")
            )
            if canonical not in found:
                found.append(canonical)
    return found


def detect_seniority(text: str) -> str | None:
    """Detecta seniority por keywords en orden senior → mid → junior → intern."""
    if not text:
        return None
    haystack = text.lower()
    for level in ("senior", "mid", "junior", "intern"):
        for kw in _SENIORITY_MAP[level]:
            if kw in haystack:
                return level
    return None


def is_remote(text: str) -> bool:
    if not text:
        return False
    haystack = text.lower()
    return any(hint in haystack for hint in _REMOTE_HINTS)
