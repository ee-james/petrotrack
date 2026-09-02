import toml
import os
import threading
from typing import Any, Dict

CONFIG_PATH = "/app/config/config.toml"

_config: Dict[str, Any] = {}
_config_mtime: float | None = None
_lock = threading.Lock()


def load_config() -> Dict[str, Any]:
    global _config, _config_mtime

    with _lock:
        try:
            mtime = os.path.getmtime(CONFIG_PATH)
        except FileNotFoundError:
            return _config

        if _config_mtime is None or mtime != _config_mtime:
            _config = toml.load(CONFIG_PATH)
            _config_mtime = mtime

    return _config


def get_config() -> Dict[str, Any]:
    return load_config()
