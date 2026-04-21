"""Wrapper sync sobre anthropic.Anthropic con prompt caching y retries."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anthropic

from atalaya.config import load_api_key

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger("atalaya.generators")

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2000


class ConfigError(RuntimeError):
    """Config o credenciales ausentes o invalidas."""


@dataclass(frozen=True)
class ClaudeUsage:
    """Tokens usados en una llamada a la API de Claude."""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int

    def summary(self) -> str:
        return (
            f"in={self.input_tokens} out={self.output_tokens} "
            f"cache_write={self.cache_creation_input_tokens} "
            f"cache_read={self.cache_read_input_tokens}"
        )


class ClaudeClient:
    """Cliente minimo sobre anthropic.Anthropic con prompt caching activo.

    El system prompt se estructura como una lista de bloques; el bloque estatico
    (base instructions + proyectos base) lleva `cache_control: ephemeral` para
    maximizar hits de cache entre llamadas sucesivas (letter + cv del mismo
    offer, o multiples offers del mismo usuario).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = 2,
        base_delay: float = 1.0,
    ) -> None:
        resolved_key = api_key if api_key is not None else load_api_key()
        if not resolved_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY no encontrada. Define la variable de entorno "
                "o configura [anthropic] api_key en config.toml."
            )
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self._model = model
        self._max_retries = max_retries
        self._base_delay = base_delay
        self.last_usage: ClaudeUsage | None = None

    @property
    def model(self) -> str:
        return self._model

    def generate(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """Llama a messages.create con prompt caching y retries transitorios.

        - `system` se envia como un unico bloque con cache_control ephemeral
          (es el prefijo estable que queremos cachear).
        - `user` se envia como mensaje user sin cache_control (varia por offer).
        """
        system_blocks: Sequence[anthropic.types.TextBlockParam] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=model or self._model,
                    max_tokens=max_tokens,
                    system=system_blocks,
                    messages=[{"role": "user", "content": user}],
                )
                usage = ClaudeUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    cache_creation_input_tokens=(
                        response.usage.cache_creation_input_tokens or 0
                    ),
                    cache_read_input_tokens=(response.usage.cache_read_input_tokens or 0),
                )
                self.last_usage = usage
                logger.info("claude usage: %s", usage.summary())
                return _extract_text(response)
            except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
                if isinstance(exc, anthropic.APIStatusError) and exc.status_code < 500:
                    raise
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                delay = self._base_delay * (2**attempt)
                logger.warning(
                    "claude transient error (%s); retry %d/%d in %.1fs",
                    type(exc).__name__,
                    attempt + 1,
                    self._max_retries,
                    delay,
                )
                time.sleep(delay)
            except anthropic.APIConnectionError as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                delay = self._base_delay * (2**attempt)
                logger.warning(
                    "claude connection error; retry %d/%d in %.1fs",
                    attempt + 1,
                    self._max_retries,
                    delay,
                )
                time.sleep(delay)

        assert last_exc is not None
        raise last_exc


def _extract_text(response: anthropic.types.Message) -> str:
    chunks: list[str] = []
    for block in response.content:
        if block.type == "text":
            chunks.append(block.text)
    return "".join(chunks).strip()
