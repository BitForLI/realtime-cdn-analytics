"""Input models and parsers for detector evaluation runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


NODE_FAULT_TYPES = {
    "node_latency_spike",
    "node_5xx_spike",
    "isp_node_degradation",
    "capacity_pressure",
}


@dataclass(frozen=True)
class Fault:
    fault_type: str
    start: datetime
    end: datetime
    target: str
    network: str | None


@dataclass(frozen=True)
class Metric:
    run_id: str
    window_start: datetime
    window_end: datetime
    location: str
    network_id: str
    node_id: str
    requests: int
    error_rate: float
    cache_hit_ratio: float
    p95_ttfb_ms: float

    @property
    def key(self) -> tuple[str, str, str]:
        return self.location, self.network_id, self.node_id


def parse_time(value: str) -> datetime:
    normalized = value.strip().replace(" ", "T")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_duration(value: str) -> timedelta:
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    normalized = value.strip().lower()
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", normalized)
    if not parts or "".join(number + unit for number, unit in parts) != normalized:
        raise ValueError(f"unsupported duration: {value}")
    return timedelta(seconds=sum(float(number) * units[unit] for number, unit in parts))


def load_faults(path: Path, manifest_path: Path | None = None) -> list[Fault]:
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        return [
            Fault(
                fault_type=str(label["type"]),
                start=parse_time(str(label["start"])),
                end=parse_time(str(label["end"])),
                target=str(label.get("target", "")),
                network=str(label["network"]) if label.get("network") else None,
            )
            for label in manifest.get("expected_label_windows", [])
            if label["type"] in NODE_FAULT_TYPES
        ]

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    start = parse_time(str(payload["start_time"]))
    faults = []
    for scenario in payload.get("scenarios", []):
        if scenario["type"] not in NODE_FAULT_TYPES:
            continue
        fault_start = start + parse_duration(str(scenario["at"]))
        faults.append(
            Fault(
                fault_type=scenario["type"],
                start=fault_start,
                end=fault_start + parse_duration(str(scenario["duration"])),
                target=str(scenario.get("target", "")),
                network=str(scenario["network"]) if scenario.get("network") else None,
            )
        )
    return faults


def load_metrics(run_id: str, path: Path) -> list[Metric]:
    metrics: list[Metric] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            metrics.append(
                Metric(
                    run_id=run_id,
                    window_start=parse_time(str(row["window_start"])),
                    window_end=parse_time(str(row["window_end"])),
                    location=str(row["location"]),
                    network_id=str(row["network_id"]),
                    node_id=str(row["node_id"]),
                    requests=int(row["requests"]),
                    error_rate=float(row["error_5xx_rate"]),
                    cache_hit_ratio=float(row["cache_hit_ratio"]),
                    p95_ttfb_ms=float(row["ttfb_p95_ms"]),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error
    return sorted(metrics, key=lambda metric: (metric.window_end, metric.key))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
