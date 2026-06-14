"""Configuration loader.
Reads config.yaml from the project root, parses it with PyYAML,
and converts it into a strongly-typed AppConfig via Pydantic.
Other modules (api, router, inference) should always go through
get_config() instead of opening config.yaml directly — this keeps
the project to one source of truth for configuration.
"""

from functools import lru_cache
from pathlib import Path

import yaml

from app.schemas import AppConfig

# Project root = the directory that contains config.yaml.
# __file__ = .../LLMRouter/app/core/config.py
#   .parent           = .../LLMRouter/app/core
#   .parent.parent    = .../LLMRouter/app
#   .parent.parent.parent = .../LLMRouter   <- this is the project root
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.yaml"

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Read config.yaml once and return a cached AppConfig.
    The lru_cache decorator means the YAML file is parsed exactly once
    per process; every subsequent call returns the same object instantly.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.yaml not found at {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw: dict = yaml.safe_load(f)

    return AppConfig.model_validate(raw)


if __name__ == '__main__':
    cfg = get_config()
    print("[1] api.host =", cfg.api.host)
    print("[2] api.port =", cfg.api.port)
    print("[3] router.default_model =", cfg.router.default_model)
    print("[4] available models:", list(cfg.router.models.keys()))
    print("[5] coding-pro cost_per_1k_output =",
          cfg.router.models["coding-pro"].cost_per_1k_output)
    print("[6] coding-pro capabilities =",
          cfg.router.models["coding-pro"].capabilities)
    print()
    print("Calling get_config() again returns the same cached object:")
    print("  is same object?", get_config() is cfg)