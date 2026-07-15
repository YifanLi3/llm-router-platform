"""Central logging configuration for the LLM Router.

Called ONCE at process startup from `app.main`. Library modules
(routers, engines, providers) must NOT call this themselves --
they only do `logger = logging.getLogger(__name__)`.
"""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False

# Default format includes level, logger name (dotted module path),
# and the message. `extra={...}` keys don't appear unless you list
# them explicitly, so we render them via a small filter below.
_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"


class _ExtraFieldsFilter(logging.Filter):
    """Append any `extra={...}` fields to the message tail as key=value pairs.

    Keeps the format string simple while still surfacing structured data
    in dev / CI logs. In production you'd swap to a JSON handler instead.
    """

    _RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys())

    def filter(self, record: logging.LogRecord) -> bool:
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self._RESERVED and not k.startswith("_")
        }
        if extras:
            record.msg = f"{record.msg}  " + " ".join(
                f"{k}={v!r}" for k, v in extras.items()
            )
        return True


def configure_logging(level: str | int | None = None) -> None:
    """Idempotent: safe to call multiple times, only configures once.

    Level resolution order:
      1. explicit `level` argument
      2. env var LOG_LEVEL
      3. INFO
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = level or os.getenv("LOG_LEVEL", "INFO")
    if isinstance(resolved, str):
        resolved = resolved.upper()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
    handler.addFilter(_ExtraFieldsFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved)

    # Silence over-chatty deps (adjust as needed).
    logging.getLogger("uvicorn.access").setLevel("WARNING")

    _CONFIGURED = True
    logging.getLogger(__name__).info("logging configured", extra={"level": resolved})