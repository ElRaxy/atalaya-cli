"""Clientes de generación con Claude.

Atalaya soporta dos backends:

1. **`cli` (DEFAULT)** — invoca `claude -p` por subprocess. Tira de la suscripción
   Claude Code del usuario (Pro/Max/Team). Sin coste API directo. Auth via OAuth
   keychain del CLI ya iniciado con `claude login`.

2. **`api`** — usa el SDK `anthropic`. Requiere `ANTHROPIC_API_KEY` propia y se
   factura aparte. Útil para CI o usuarios sin Claude Code instalado.

Selección por config (`<config_dir>/config.toml`):

```toml
[claude]
backend = "cli"           # o "api"
model   = "claude-sonnet-4-6"
```

Ambos clientes exponen la misma firma `generate(system, user, max_tokens) -> str`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from atalaya.config import load_api_key, load_config

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

logger = logging.getLogger("atalaya.generators")

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2000
DEFAULT_BACKEND = "cli"
_CLI_TIMEOUT_S = 180


class ConfigError(RuntimeError):
    """Config o credenciales ausentes o invalidas."""


@dataclass(frozen=True)
class ClaudeUsage:
    """Tokens usados en una llamada a Claude (best-effort, varia entre backends)."""

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


class ClaudeBackend(Protocol):
    """Interfaz común para los backends de generación."""

    last_usage: ClaudeUsage | None

    @property
    def model(self) -> str: ...

    def generate(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str: ...


class ClaudeCodeClient:
    """Backend subprocess sobre `claude -p` (Claude Code CLI).

    Tira de la suscripción Claude Code (OAuth keychain). No requiere
    `ANTHROPIC_API_KEY`. El user_prompt va por stdin para evitar límite de
    argv y caracteres problemáticos.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        executable: str | None = None,
        timeout_s: int = _CLI_TIMEOUT_S,
    ) -> None:
        resolved = executable or shutil.which("claude")
        if not resolved:
            raise ConfigError(
                "ejecutable `claude` no encontrado en PATH. Instala Claude Code "
                "(https://docs.anthropic.com/claude-code) o cambia [claude] backend a 'api'."
            )
        self._executable = resolved
        self._model = model
        self._timeout_s = timeout_s
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
        # max_tokens no es un flag de `claude -p` (lo decide el modelo). Lo aceptamos
        # por compatibilidad de interfaz pero solo se aplica en backend `api`.
        del max_tokens

        cmd = [
            self._executable,
            "-p",
            "--output-format",
            "json",
            "--model",
            model or self._model,
            "--system-prompt",
            system,
            "--no-session-persistence",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=user,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConfigError(
                f"claude -p timeout tras {self._timeout_s}s — modelo lento o no responde"
            ) from exc
        except FileNotFoundError as exc:
            raise ConfigError(
                f"no se pudo ejecutar `{self._executable}`: {exc}"
            ) from exc

        if proc.returncode != 0:
            raise ConfigError(
                f"claude -p exit {proc.returncode}: {proc.stderr.strip()[:400]}"
            )

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"respuesta claude -p no es JSON válido: {exc}\nStdout: {proc.stdout[:400]}"
            ) from exc

        if payload.get("is_error"):
            raise ConfigError(
                f"claude -p devolvió error: {payload.get('result', '<sin detalle>')[:300]}"
            )

        result = payload.get("result")
        if not isinstance(result, str):
            raise ConfigError(
                f"claude -p sin campo 'result' string: {str(payload)[:300]}"
            )

        usage_raw = payload.get("usage") or {}
        self.last_usage = ClaudeUsage(
            input_tokens=int(usage_raw.get("input_tokens", 0)),
            output_tokens=int(usage_raw.get("output_tokens", 0)),
            cache_creation_input_tokens=int(
                usage_raw.get("cache_creation_input_tokens", 0)
            ),
            cache_read_input_tokens=int(usage_raw.get("cache_read_input_tokens", 0)),
        )
        logger.info("claude-cli usage: %s", self.last_usage.summary())
        return result.strip()


class ClaudeApiClient:
    """Backend SDK anthropic. Requiere `ANTHROPIC_API_KEY`.

    Mantiene el comportamiento histórico: prompt caching activo en system block,
    retries en errores transitorios 5xx / rate limit.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_retries: int = 2,
        base_delay: float = 1.0,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ConfigError(
                "backend 'api' requiere el paquete `anthropic`. "
                "Instala con `pip install atalaya-cli[api]`."
            ) from exc

        resolved_key = api_key if api_key is not None else load_api_key()
        if not resolved_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY no encontrada. Define la variable de entorno "
                "o configura [anthropic] api_key en config.toml. "
                "(O cambia [claude] backend a 'cli' para usar Claude Code subscription.)"
            )
        self._anthropic = anthropic
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
        anthropic = self._anthropic
        system_blocks: Sequence[Any] = [
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
                logger.info("claude-api usage: %s", usage.summary())
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


def _extract_text(response: object) -> str:
    """Extrae texto plano del Message de anthropic."""
    chunks: list[str] = []
    content = getattr(response, "content", None) or []
    for block in content:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", ""))
    return "".join(chunks).strip()


def make_client(
    backend: str | None = None,
    model: str | None = None,
) -> ClaudeBackend:
    """Crea el backend configurado en `config.toml` (default `cli`).

    Permite override por argumento o por env var `ATALAYA_CLAUDE_BACKEND`.
    """
    if backend is None:
        env_override = os.environ.get("ATALAYA_CLAUDE_BACKEND")
        if env_override:
            backend = env_override.lower()
        else:
            cfg = load_config()
            claude_cfg = cfg.get("claude")
            if isinstance(claude_cfg, dict):
                backend = str(claude_cfg.get("backend", DEFAULT_BACKEND)).lower()
            else:
                backend = DEFAULT_BACKEND

    if model is None:
        cfg = load_config()
        claude_cfg = cfg.get("claude")
        if isinstance(claude_cfg, dict):
            model = str(claude_cfg.get("model", DEFAULT_MODEL))
        else:
            model = DEFAULT_MODEL

    if backend == "cli":
        return ClaudeCodeClient(model=model)
    if backend == "api":
        return ClaudeApiClient(model=model)
    raise ConfigError(
        f"backend desconocido '{backend}'. Valores válidos: 'cli', 'api'."
    )


# Alias retrocompatible: imports antiguos siguen funcionando.
ClaudeClient = ClaudeApiClient
