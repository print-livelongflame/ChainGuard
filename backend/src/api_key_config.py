"""Manage local API-key constants without returning secrets to web clients."""

import ast
import os
import tempfile
from pathlib import Path
from typing import Mapping


API_KEYS_PATH = Path(__file__).resolve().parents[1] / "api_keys" / "api_keys.py"
API_KEY_NAMES = (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "ETHERSCAN_API_KEY",
    "DETECTOR_API_KEY",
)


def _read_file_values() -> dict[str, str]:
    values = {name: "" for name in API_KEY_NAMES}
    try:
        source = API_KEYS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return values
    except OSError as error:
        raise ValueError("Could not read backend/api_keys/api_keys.py.") from error

    try:
        module = ast.parse(source, filename=str(API_KEYS_PATH))
    except SyntaxError as error:
        raise ValueError("backend/api_keys/api_keys.py is not valid Python.") from error

    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue

        for target in targets:
            if not isinstance(target, ast.Name) or target.id not in values:
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if isinstance(value, str):
                values[target.id] = value

    return values


def get_api_key(name: str) -> str:
    if name not in API_KEY_NAMES:
        raise ValueError("Unsupported API key name.")

    value = os.environ.get(name, "").strip()
    if value and value.casefold() != "enter key here":
        return value

    value = _read_file_values()[name].strip()
    return "" if value.casefold() == "enter key here" else value


def get_api_key_status() -> dict[str, bool]:
    return {name: bool(get_api_key(name)) for name in API_KEY_NAMES}


def save_api_keys(updates: Mapping[str, str | None]) -> dict[str, bool]:
    values = _read_file_values()
    for name, value in updates.items():
        if name not in API_KEY_NAMES:
            raise ValueError("Unsupported API key name.")
        if value is None:
            values[name] = ""
        else:
            normalized = value.strip()
            if len(normalized) > 4096:
                raise ValueError(f"{name} must be 4096 characters or fewer.")
            values[name] = normalized

    API_KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_file = API_KEYS_PATH.parent / "__init__.py"
    init_file.touch(exist_ok=True)
    source = "\n".join(
        f"{name} = {values[name]!r}" for name in API_KEY_NAMES
    ) + "\n"

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=API_KEYS_PATH.parent,
            prefix=".api_keys-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(source)
        os.replace(temporary_path, API_KEYS_PATH)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ValueError("Could not save backend/api_keys/api_keys.py.") from error

    return get_api_key_status()


def apply_api_key_updates(updates: Mapping[str, str | None]) -> None:
    for name, value in updates.items():
        if value is None or not value.strip():
            os.environ.pop(name, None)
        else:
            os.environ[name] = value.strip()
