"""Pure backend planning. Never imports or starts a model runtime."""

from urllib.parse import urlparse

from .configuration import LOCAL_HOSTS


def backend_environment(env, *, authorized_model_usage=False):
    if not authorized_model_usage:
        raise PermissionError("BLOCKED: explicit generative model-use authorization required")
    model = env.get("SIIP_EXTRACTION_MODEL", "")
    if not model or len(model) > 160:
        raise ValueError("Explicit extraction model identifier required")
    provider = env.get("LLM_PROVIDER", "openai").lower()
    if provider in {"local", "hf", "huggingface", "vllm", "hf_legacy"}:
        return {
            "LLM_PROVIDER": provider,
            "HF_CONCEPTS_MODEL": model,
            "LLM_MODEL": model,
            "HF_TRUST_REMOTE_CODE": "0",
        }
    if provider == "openai":
        endpoint = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        parsed = urlparse(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid extraction API endpoint")
        if parsed.hostname in LOCAL_HOSTS:
            # The SDK requires a nonempty string, not a paid provider account.
            # Upstream uses Responses: server feature support is a separate gate.
            return {
                "LLM_PROVIDER": "openai",
                "OPENAI_BASE_URL": endpoint,
                "OPENAI_API_KEY": env.get("OPENAI_API_KEY") or "local-placeholder",
                "OPENAI_CONCEPTS_MODEL": model,
            }
        if parsed.scheme != "https":
            raise ValueError("Remote extraction requires HTTPS")
        key_name = "OPENAI_API_KEY"
        result = {
            "LLM_PROVIDER": provider,
            "OPENAI_BASE_URL": endpoint,
            "OPENAI_CONCEPTS_MODEL": model,
        }
    elif provider in {"anthropic", "claude"}:
        key_name = "ANTHROPIC_API_KEY"
        result = {"LLM_PROVIDER": provider, "ANTHROPIC_CONCEPTS_MODEL": model}
    else:
        raise ValueError("Unsupported extraction backend")
    if env.get("SIIP_ALLOW_PAID_API") != "I_AUTHORIZE_PAID_MODEL_USAGE" or not env.get(key_name):
        raise PermissionError(
            "BLOCKED: remote extraction requires explicit paid-use consent and credential"
        )
    result[key_name] = env[key_name]
    return result
