"""Validated inference configuration. Presence of a key never authorizes spending."""

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "deterministic"
    base_url: str = "http://127.0.0.1:8000/v1"
    model: str = "local-model"
    api_key: str = ""
    timeout_seconds: float = 8.0
    max_tokens: int = 350
    retries: int = 0
    allow_paid: bool = False

    def validate(self) -> None:
        if self.provider not in {"deterministic", "local", "compatible"}:
            raise ValueError("Unknown feedback provider")
        if (
            not 0.1 <= self.timeout_seconds <= 60.0
            or not 32 <= self.max_tokens <= 500
            or not 0 <= self.retries <= 2
        ):
            raise ValueError("Inference limits outside approved local bounds")
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid provider endpoint")
        if self.provider != "deterministic" and parsed.hostname not in LOCAL_HOSTS:
            if not self.allow_paid or self.provider != "compatible" or parsed.scheme != "https":
                raise ValueError("Remote HTTPS inference needs explicit paid-use authorization")
            if not self.api_key:
                raise ValueError("Approved remote provider requires an environment API key")
        if not self.model or len(self.model) > 160:
            raise ValueError("Invalid model identifier")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ProviderConfig":
        result = cls(
            provider=env.get("SIIP_FEEDBACK_PROVIDER", "deterministic"),
            base_url=env.get("SIIP_LLM_BASE_URL", "http://127.0.0.1:8000/v1"),
            model=env.get("SIIP_LLM_MODEL", "local-model"),
            api_key=env.get("SIIP_LLM_API_KEY", ""),
            timeout_seconds=float(env.get("SIIP_LLM_TIMEOUT_SECONDS", "8")),
            max_tokens=int(env.get("SIIP_LLM_MAX_TOKENS", "350")),
            retries=int(env.get("SIIP_LLM_RETRIES", "0")),
            allow_paid=env.get("SIIP_ALLOW_PAID_API") == "I_AUTHORIZE_PAID_MODEL_USAGE",
        )
        result.validate()
        return result


def read_env_file(path: str, base: Mapping[str, str]) -> dict[str, str]:
    """Read literal KEY=VALUE pairs; never execute shell or interpolate variables."""
    from pathlib import Path

    values: dict[str, str] = {}
    target = Path(path)
    if target.exists():
        for raw in target.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or not key.replace("_", "").isalnum():
                raise ValueError("Invalid environment file entry")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            values[key] = value
    values.update(base)
    return values
