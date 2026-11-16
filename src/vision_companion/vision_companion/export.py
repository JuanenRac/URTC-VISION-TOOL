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

import ipaddress
import json
import logging
import os
import urllib.error
import urllib.parse
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The token goes to the address that was given and nowhere else: a redirect is an answer, not a place to follow."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)
LOG = logging.getLogger("vision_companion.export")


def plain_datalake_refusal(base_url: str) -> str | None:
    """None when the write token may be sent to ``base_url`` (https, or plain http to this same machine), otherwise the reason."""
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or ""
    local = host == "localhost"
    if not local:
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
    if parsed.scheme == "https" and host or parsed.scheme == "http" and local:
        return None
    return "the write token must not cross a network in clear: use an https:// address, or http:// to this same machine"


def post_samples(base_url: str, samples: list[dict[str, Any]], token_env: str, timeout_s: float = 10.0) -> int:
    """POST every sample to ``<base_url>/ingest`` with the bearer token held in the environment variable ``token_env``.

    Returns how many were accepted; raises ExportError on the first refusal or network failure (naming the status, never the token). A redirect is never followed. A plain
    http address to another machine is accepted with a warning unless ``UVIS_ALLOW_PLAIN_DATALAKE=0`` refuses it.
    """
    token = os.environ.get(token_env, "")
    if not token:
        raise ExportError(f"the environment variable {token_env} holds no token")
    if not base_url.startswith(("http://", "https://")):
        raise ExportError("the datalake address must start with http:// or https://")
    problem = plain_datalake_refusal(base_url)
    if problem:
        if os.environ.get("UVIS_ALLOW_PLAIN_DATALAKE", "1").strip() == "0":
            raise ExportError(f"{problem} (UVIS_ALLOW_PLAIN_DATALAKE=0)")
        LOG.warning("%s; accepted because UVIS_ALLOW_PLAIN_DATALAKE is not 0", problem)
    accepted = 0
    for sample in samples:
        request = urllib.request.Request(
            base_url.rstrip("/") + "/ingest", data=json.dumps(sample).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        try:
            with _OPENER.open(request, timeout=timeout_s) as response:  # noqa: S310 - the scheme is checked above
                if response.status >= 300:
                    raise ExportError(f"the datalake answered {response.status}")
        except urllib.error.HTTPError as error:
            raise ExportError(f"the datalake refused a sample with status {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ExportError(f"the datalake could not be reached: {type(error).__name__}") from error
        accepted += 1
    return accepted
