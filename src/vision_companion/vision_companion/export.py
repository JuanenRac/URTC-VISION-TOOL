# =============================================================================
# URTC-VISION-TOOL - vision_companion export of the ROI series: export.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Turns an inspection report into the samples of a time series: the minimum, maximum, mean and 95th percentile of every
# region, for every task, so the quality of a run can be traced afterwards. Three forms:
#   * the samples the HYDRA-UMC datalake takes on POST /ingest ({sourceId, kind, timestamp in milliseconds, fields});
#   * one JSON line per sample, for a file;
#   * a map of OPC-UA nodes (browse path -> value), which a gateway publishes; this module does not run an OPC-UA server.
# The token for the datalake is read from an environment variable whose name the caller gives; it is never printed.
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .inspection import Report

KIND = "vision_thermal_roi"
DEFAULT_SOURCE = "urtc-vision-tool"
STATS = ("min_c", "max_c", "mean_c", "p95_c")
MIN_TIMESTAMP_MS = 100_000_000_000   # the datalake refuses anything earlier (a producer that sent seconds)


class ExportError(ValueError):
    """The export could not be made or delivered."""


def samples_from_report(report: Report, timestamp_ms: int, source_id: str = DEFAULT_SOURCE, task: str = "") -> list[dict[str, Any]]:
    """One sample per task: the fields are ``<ref>.<statistic>``, the statistics of the regions measured for that task.

    Regions without data are left out (a missing value is not a number); ``task`` names the run when a component has no task of its own.
    """
    if isinstance(timestamp_ms, bool) or not isinstance(timestamp_ms, int) or timestamp_ms < MIN_TIMESTAMP_MS:
        raise ExportError("timestamp_ms must be a Unix time in milliseconds")
    if not source_id:
        raise ExportError("source_id must not be empty")
    by_task: dict[str, dict[str, float]] = {}
    for result in report.results:
        if result.stats.is_empty:
            continue
        fields = by_task.setdefault(result.task or task or "default", {})
        values = {"min_c": result.stats.min_c, "max_c": result.stats.max_c, "mean_c": result.stats.mean_c, "p95_c": result.stats.p95_c}
        for name in STATS:
            fields[f"{result.ref}.{name}"] = round(float(values[name]), 3)
    return [{"sourceId": f"{source_id}/{name}", "kind": KIND, "timestamp": timestamp_ms, "fields": fields} for name, fields in sorted(by_task.items())]


def to_jsonl(samples: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(sample, sort_keys=True) + "\n" for sample in samples)


def opcua_nodes(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Browse path ``URTC/Vision/<task>/<ref>/<statistic>`` -> value, type and source time, for a gateway that publishes OPC-UA."""
    nodes: dict[str, dict[str, Any]] = {}
    for sample in samples:
        task = sample["sourceId"].split("/", 1)[-1]
        stamp = datetime.fromtimestamp(sample["timestamp"] / 1000, tz=timezone.utc).isoformat()
        for field_name, value in sample["fields"].items():
            ref, _, stat = field_name.rpartition(".")
            nodes[f"URTC/Vision/{task}/{ref}/{stat}"] = {"value": value, "type": "Double", "source_time": stamp}
    return nodes


def post_samples(base_url: str, samples: list[dict[str, Any]], token_env: str, timeout_s: float = 10.0) -> int:
    """POST every sample to ``<base_url>/ingest`` with the bearer token held in the environment variable ``token_env``.

    Returns how many were accepted; raises ExportError on the first refusal or network failure (naming the status, never the token).
    """
    token = os.environ.get(token_env, "")
    if not token:
        raise ExportError(f"the environment variable {token_env} holds no token")
    if not base_url.startswith(("http://", "https://")):
        raise ExportError("the datalake address must start with http:// or https://")
    accepted = 0
    for sample in samples:
        request = urllib.request.Request(
            base_url.rstrip("/") + "/ingest", data=json.dumps(sample).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - the scheme is checked above
                if response.status >= 300:
                    raise ExportError(f"the datalake answered {response.status}")
        except urllib.error.HTTPError as error:
            raise ExportError(f"the datalake refused a sample with status {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ExportError(f"the datalake could not be reached: {type(error).__name__}") from error
        accepted += 1
    return accepted
