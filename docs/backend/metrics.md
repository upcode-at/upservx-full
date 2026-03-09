# Metrics & Monitoring

**File:** `upservx-service/metrics_collector.py`
**API sub-module:** `upservx-service/api/metrics.py`

**Required permission:** Read-only (any authenticated user)

---

## Overview

The metrics module collects system, container, and VM performance data in real time. The frontend uses these metrics for the dashboard overview and detailed views.

---

## System Metrics

Collected via `psutil`:

```python
class SystemMetrics(BaseModel):
    cpu_percent: float      # Overall CPU utilization
    cpu_per_core: List[float]
    cpu_freq_mhz: float
    cpu_count: int
    memory_total: int
    memory_used: int
    memory_available: int
    memory_percent: float
    swap_total: int
    swap_used: int
    swap_percent: float
    disk_partitions: List[DiskMetric]
    network_interfaces: List[NetworkMetric]
    uptime_seconds: int
    load_average: List[float]   # 1m, 5m, 15m
    boot_time: datetime
    temperature: List[TempMetric]
```

---

## Process Metrics

```python
class ProcessMetric(BaseModel):
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_rss: int
    memory_vms: int
    threads: int
    user: str
    cmdline: str
    create_time: datetime
```

---

## Docker Metrics

Data via `docker stats --no-stream --format json`:

```python
class ContainerMetric(BaseModel):
    name: str
    cpu_percent: float
    memory_usage: int
    memory_limit: int
    memory_percent: float
    net_rx: int
    net_tx: int
    block_read: int
    block_write: int
    pids: int
```

---

## Historical Data

The metrics module maintains a **ring buffer** (in RAM):

- Maximum 1440 data points per metric (= 24 hours at 1-minute resolution)
- Key: metric type + resource identifier
- Stored as `List[Tuple[timestamp, value]]`

```python
HISTORY_SIZE = 1440
history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY_SIZE))
```

---

## Metric Collection Loop

A background task collects metrics at configurable intervals:

```python
async def metrics_loop():
    while True:
        metrics = collect_all_metrics()
        store_to_history(metrics)
        if check_thresholds(metrics):
            send_notification_event(...)
        await asyncio.sleep(settings.metrics_interval_seconds)
```

Default interval: **60 seconds**

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/metrics` | Current system snapshot |
| `GET` | `/metrics/cpu` | CPU metrics with history |
| `GET` | `/metrics/memory` | Memory metrics with history |
| `GET` | `/metrics/disk` | Disk metrics |
| `GET` | `/metrics/network` | Network traffic |
| `GET` | `/metrics/processes` | Process list |
| `GET` | `/metrics/containers` | Container statistics |
| `GET` | `/metrics/temperature` | Hardware temperatures |
| `WebSocket` | `/metrics/ws` | Real-time metrics stream |

---

## Threshold Alerts

Configurable thresholds in `settings.json`:

```json
{
  "alert_cpu_percent": 90,
  "alert_memory_percent": 85,
  "alert_disk_percent": 90
}
```

When exceeded, a notification event is fired (see [Notifications](./notifications.md)).
