"""Persistent cache helpers for successful fetcher results."""

import hashlib
import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CACHE_DIR = (
    Path(__file__).resolve().parent.parent
    / "fetchers"
    / "cache"
    / "fetcher_results"
)


def build_fetcher_cache_key(
    name: str,
    module_name: str,
    function_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    """Hash the fetcher identity and arguments without storing them in filenames."""
    normalized_args = tuple(
        value.lower()
        if isinstance(value, str) and value.startswith("0x")
        else value
        for value in args
    )
    cache_identity = json.dumps(
        [name, module_name, function_name, normalized_args, kwargs],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(cache_identity.encode("utf-8")).hexdigest()


def _cache_metadata(source: str, fetched_at: float, ttl_seconds: int) -> dict:
    age_seconds = max(0, int(time.time() - fetched_at))
    return {
        "source": source,
        "fetched_at": datetime.fromtimestamp(
            fetched_at, timezone.utc
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "age_seconds": age_seconds,
        "ttl_seconds": ttl_seconds,
    }


def read_fetcher_cache(
    cache_key: str,
    ttl_seconds: int,
    cache_dir: Path = CACHE_DIR,
) -> tuple[Any | None, dict]:
    """Return fresh cached data, or network-source metadata on a cache miss."""
    cache_path = cache_dir / f"{cache_key}.json"
    try:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except FileNotFoundError:
        return None, {"source": "network", "ttl_seconds": ttl_seconds}
    except (OSError, json.JSONDecodeError) as error:
        return None, {
            "source": "network",
            "ttl_seconds": ttl_seconds,
            "warning": f"Could not read fetcher cache: {error}",
        }

    fetched_at = payload.get("fetched_at") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or not isinstance(fetched_at, (int, float))
        or not math.isfinite(fetched_at)
        or fetched_at < 0
        or fetched_at > time.time() + 24 * 60 * 60
        or "data" not in payload
    ):
        return None, {
            "source": "network",
            "ttl_seconds": ttl_seconds,
            "warning": "Fetcher cache entry has an invalid format.",
        }

    metadata = _cache_metadata("disk", fetched_at, ttl_seconds)
    if time.time() - fetched_at <= ttl_seconds:
        return payload["data"], metadata

    metadata["source"] = "network"
    metadata["stale"] = True
    return None, metadata


def write_fetcher_cache(
    cache_key: str,
    data: Any,
    ttl_seconds: int,
    cache_dir: Path = CACHE_DIR,
) -> dict:
    """Persist a successful result atomically and return its provenance."""
    fetched_at = time.time()
    metadata = _cache_metadata("network", fetched_at, ttl_seconds)
    temporary_path = None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps({"fetched_at": fetched_at, "data": data})
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_dir,
            prefix=f"{cache_key}.",
            suffix=".tmp",
            delete=False,
        ) as cache_file:
            temporary_path = Path(cache_file.name)
            cache_file.write(serialized)
        os.replace(temporary_path, cache_dir / f"{cache_key}.json")
    except (OSError, TypeError, ValueError) as error:
        metadata["warning"] = f"Could not write fetcher cache: {error}"
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as error:
                metadata.setdefault(
                    "warning", f"Could not clean up temporary cache file: {error}"
                )

    return metadata
