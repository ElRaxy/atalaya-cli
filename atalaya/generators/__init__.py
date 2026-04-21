"""Generadores IA: carta de presentacion y variante de CV (Claude API)."""

from __future__ import annotations

from atalaya.generators.claude_client import ClaudeClient, ClaudeUsage, ConfigError
from atalaya.generators.cv_variant import generate_cv_variant, load_base_cv
from atalaya.generators.letter import generate_letter

__all__ = [
    "ClaudeClient",
    "ClaudeUsage",
    "ConfigError",
    "generate_cv_variant",
    "generate_letter",
    "load_base_cv",
]
