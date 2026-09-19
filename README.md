# Real-Time CDN Analytics

This local CDN analytics system studies event-time behaviour under late data, duplicate delivery, replay, and component failure. It turns synthetic delivery, routing, and player events into ClickHouse metrics, Grafana dashboards, and short-lived routing recommendations that remain in shadow mode.

## Product at a glance

| | |
| --- | --- |
| **Users** | CDN and platform engineers investigating delivery quality and routing decisions |
| **Problem** | Late, duplicated, invalid, or replayed events can produce misleading operational metrics |
| **Input** | Versioned synthetic CDN delivery, routing, and player events |
| **Output** | Event-time metrics, a Grafana dashboard, and explainable shadow-routing recommendations |
| **Safety boundary** | Recommendations are recorded for review and never change live DNS routing |

The main product decision is to keep analysis outside the request path. StreamPulse can explain what it would recommend, why, and for how long without making content delivery depend on the analytics pipeline.

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

## Evidence behind project claims

The [Flink job](jobs/cdn-analytics/src/main/java/com/streampulse/analytics/CdnAnalyticsJob.java),
[event-ID deduplicator](jobs/cdn-analytics/src/main/java/com/streampulse/analytics/parse/EventIdDeduplicator.java),
and [delivery parser](jobs/cdn-analytics/src/main/java/com/streampulse/analytics/parse/DeliveryEventParser.java)
implement the event-time and dead-letter path. The
[Kafka/Flink integration report](experiments/reports/flink-integration/report.md)
records the fixed-seed counts; the
[lateness experiment](experiments/results/watermark-lateness/report.md)
records one allowed-late revision and one too-late audit event.

The [ClickHouse schema](infra/clickhouse/init/001_schema.sql) and
[integration report](experiments/reports/clickhouse-grafana/report.md) support
the storage and dashboard claims. The Go
[recommendation service](services/recommendation-api/internal/app/service.go),
[scorer](services/recommendation-api/internal/scoring/scorer.go), and
[end-to-end report](experiments/reports/recommendation-api/report.md) support
the shadow-recommendation claims. These are local synthetic results, not
production throughput or evidence of improved live routing.

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
