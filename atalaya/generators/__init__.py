"""Generadores IA: carta de presentacion y variante de CV.

Backend por defecto: Claude Code subscription via `claude -p` subprocess.
Configurable a `api` (SDK anthropic + ANTHROPIC_API_KEY) en `config.toml`.
"""

from __future__ import annotations

from atalaya.generators.claude_client import (
    ClaudeApiClient,
    ClaudeBackend,
    ClaudeClient,  # alias retrocompat
    ClaudeCodeClient,
    ClaudeUsage,
    ConfigError,
    make_client,
)
from atalaya.generators.cv_variant import generate_cv_variant, load_base_cv
from atalaya.generators.letter import generate_letter

__all__ = [
    "ClaudeApiClient",
    "ClaudeBackend",
    "ClaudeClient",
    "ClaudeCodeClient",
    "ClaudeUsage",
    "ConfigError",
    "generate_cv_variant",
    "generate_letter",
    "load_base_cv",
    "make_client",
]
