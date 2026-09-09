# StreamPulse

StreamPulse is a local CDN analytics system built to study event-time behaviour under late data, duplicate delivery, replay, and component failure. It turns synthetic delivery, routing, and player events into ClickHouse metrics, Grafana dashboards, and short-lived routing recommendations that remain in shadow mode.

The project began from an Apache Flink operations playground. The event contracts, workload generator, analytics jobs, ClickHouse pipeline, recommendation service, experiments, and dashboard were added in this repository.

## Architecture

```text
synthetic events -> Kafka -> Flink -> Kafka aggregates -> ClickHouse -> Grafana
                         |                              |
                         +-> late / invalid records    +-> recommendation API
```

## What it handles

- Versioned delivery, routing, player, and recommendation events.
- Out-of-order arrival, idle partitions, allowed-late updates, and too-late records.
- Event-ID deduplication and a separate dead-letter path for invalid input.
- Node, network, and content-window aggregates stored in ClickHouse.
- Fixed-threshold and historical EWMA/MAD detectors.
- Guardrails for stale data, unhealthy nodes, capacity, minimum candidates, weight changes, and dwell time.
- Audit records containing evidence windows, reason codes, proposed weights, acknowledgements, and observed outcomes.

Recommendations expire after two minutes and cannot change production routing.

## Verified local run

A fixed-seed integration run sent 22,800 requests through Kafka and Flink. The pipeline reached zero source lag, completed 21 observed checkpoints, and wrote 219 dead-letter records for 219 deliberately invalid events.

Additional fault tests covered:

- ClickHouse pause and backlog recovery.
- Flink TaskManager restart from a checkpoint.
- Replay of the same event IDs without duplicate aggregates.
- An idle Kafka partition followed by an allowed-late correction and a too-late event.

The measurements come from a local synthetic workload. Detailed inputs and results are retained under [`experiments`](experiments/) so the claims can be reproduced rather than taken on trust.

![StreamPulse dashboard](docs/streampulse-dashboard.png)

## Quick start

Prerequisites: Docker Desktop, PowerShell 7, Java 17 with Maven, Python 3, and Go 1.23 or newer.

Run the contract tests:

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests/schema -v
```

Start the local services and run the short demonstration:

```powershell
docker compose -f compose.yaml up -d
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo.ps1
```

The script publishes a fresh synthetic fault, runs an isolated Flink job, and checks that a recommendation reaches Kafka and ClickHouse. It leaves the reusable stack running and cancels only the isolated job.

## Useful checks

```powershell
mvn -f jobs/cdn-analytics/pom.xml test
make clickhouse-benchmark
make watermark-lateness-test
make recommendation-e2e
make detector-test
```

Some integration checks require the Compose stack. Each report records its scenario, commands, and observed result.

## Repository layout

| Path | Purpose |
| --- | --- |
| `schemas` and `contracts` | Event definitions and compatibility rules |
| `services/event-generator` | Fixed-seed synthetic workload generator |
| `jobs/cdn-analytics` | Java/Flink event-time analytics |
| `services/recommendation-api` | Go detection, scoring, guardrails, and publication |
| `infra/clickhouse` | Tables and materialised views |
| `infra/grafana` | Provisioned datasource and dashboard |
| `experiments` | Scenarios, manifests, measurements, and reports |
| `docs` | Architecture, event semantics, and verification notes |

See [`THIRD_PARTY.md`](THIRD_PARTY.md) for upstream code and licence boundaries.
