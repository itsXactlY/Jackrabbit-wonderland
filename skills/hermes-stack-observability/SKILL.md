---
name: hermes-stack-observability
category: devops
description: Monitoring and observability for the Hermes ecosystem - metrics, logs, traces, and alerting
tags: [monitoring, observability, hermes, metrics, logs, traces, alerting, prometheus, grafana]
---

# Hermes Stack Observability
Comprehensive monitoring for the entire Hermes ecosystem.

## Overview
A complete observability solution for the Hermes stack, providing metrics collection, log aggregation, distributed tracing, and alerting. Ensures system health, performance monitoring, and rapid incident response.

## Components

### 1. Metrics Collection
- **Prometheus**: Time-series metrics database
- **Node Exporter**: System-level metrics (CPU, memory, disk, network)
- **Custom Exporters**: Application-specific metrics for each Hermes component
- **Alertmanager**: Alert routing and notification

### 2. Log Aggregation
- **Loki**: Log aggregation system
- **Promtail**: Log collection agent
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Log Retention**: Configurable retention policies

### 3. Distributed Tracing
- **Jaeger**: Distributed tracing system
- **OpenTelemetry**: Instrumentation library
- **Trace Propagation**: Across Hermes components
- **Performance Analysis**: Latency breakdown and bottleneck identification

### 4. Visualization & Dashboards
- **Grafana**: Visualization platform
- **Pre-built Dashboards**: For each Hermes component
- **Custom Dashboards**: User-defined monitoring views
- **Mobile Access**: Responsive design for on-call engineers

### 5. Alerting System
- **Multi-channel Alerts**: Email, Slack, Discord, SMS, PagerDuty
- **Alert Rules**: Configurable thresholds and conditions
- **Escalation Policies**: Tiered alert routing
- **Alert Grouping**: Reduce notification fatigue

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hermes Stack Components                   │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│   Hermes    │   Neural    │    PULSE    │   Jackrabbit   │
│   Agent     │   Memory    │             │   Wonderland   │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬────────┘
       │             │             │               │
       ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                OpenTelemetry Collectors                      │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│   Metrics   │    Logs     │   Traces    │    Events       │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬────────┘
       │             │             │               │
       ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                Storage & Processing Layer                    │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│ Prometheus  │    Loki     │   Jaeger    │   Elasticsearch │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬────────┘
       │             │             │               │
       └─────────────┴─────────────┴───────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                Visualization & Alerting                      │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│   Grafana   │ Alertmanager│  Dashboards │    Reports      │
└─────────────┴─────────────┴─────────────┴─────────────────┘
```

## Installation

### Prerequisites
```bash
# Docker and Docker Compose
sudo apt update
sudo apt install docker.io docker-compose

# Or use podman
sudo apt install podman podman-compose
```

### Quick Start
```bash
# Clone repository
git clone https://github.com/itsXactlY/hermes-stack-observability.git
cd hermes-stack-observability

# Start monitoring stack
docker-compose up -d

# Access Grafana
open http://localhost:3000
# Default credentials: admin/admin
```

### Manual Installation
```bash
# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvf prometheus-2.45.0.linux-amd64.tar.gz
sudo mv prometheus-2.45.0.linux-amd64 /opt/prometheus

# Install Grafana
sudo apt install -y apt-transport-https software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install grafana

# Install Loki and Promtail
docker run -d --name loki -p 3100:3100 grafana/loki:2.9.0
docker run -d --name promtail -v /var/log:/var/log grafana/promtail:2.9.0
```

## Configuration

### Prometheus Configuration (`prometheus.yml`)
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - "alert_rules.yml"

scrape_configs:
  # Hermes Agent metrics
  - job_name: 'hermes-agent'
    static_configs:
      - targets: ['hermes-agent:8000']
    metrics_path: '/metrics'
  
  # Neural Memory metrics
  - job_name: 'neural-memory'
    static_configs:
      - targets: ['neural-memory:8001']
    metrics_path: '/metrics'
  
  # PULSE metrics
  - job_name: 'pulse-hermes'
    static_configs:
      - targets: ['pulse-hermes:8002']
    metrics_path: '/metrics'
  
  # Jackrabbit metrics
  - job_name: 'jackrabbit'
    static_configs:
      - targets: ['jackrabbit:8003']
    metrics_path: '/metrics'
  
  # System metrics
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Loki Configuration (`loki-config.yml`)
```yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /data/loki/boltdb-shipper-active
    cache_location: /data/loki/boltdb-shipper-cache
    shared_store: filesystem
  filesystem:
    directory: /data/loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

compactor:
  working_directory: /data/loki/compactor
  shared_store: filesystem
```

### Alert Rules (`alert_rules.yml`)
```yaml
groups:
  - name: hermes_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} per second"
      
      # High latency
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "95th percentile latency is {{ $value }} seconds"
      
      # Memory usage
      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024 / 1024 > 1024
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }} MB"
      
      # Disk usage
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space low"
          description: "Only {{ $value }}% disk space remaining"
      
      # Component down
      - alert: ComponentDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Component down"
          description: "{{ $labels.job }} instance {{ $labels.instance }} is down"
```

## Metrics Collection

### Hermes Agent Metrics
```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Request metrics
REQUEST_COUNT = Counter(
    'hermes_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'hermes_request_duration_seconds',
    'Request latency',
    ['method', 'endpoint']
)

# Agent metrics
AGENT_SESSIONS = Gauge(
    'hermes_active_sessions',
    'Active agent sessions'
)

TOOL_CALLS = Counter(
    'hermes_tool_calls_total',
    'Total tool calls',
    ['tool_name', 'status']
)

MEMORY_USAGE = Gauge(
    'hermes_memory_usage_bytes',
    'Memory usage in bytes'
)

# Start metrics server
start_http_server(8000)
```

### Neural Memory Metrics
- Memory operations (store, recall, think)
- Vector database performance
- Embedding generation latency
- Cache hit rates
- Storage utilization

### PULSE Metrics
- API calls per source
- Response times
- Rate limit usage
- Cache performance
- Data freshness

### Jackrabbit Metrics
- Encryption/decryption operations
- Key vault access
- Key rotation events
- Storage usage
- Performance metrics

## Dashboards

### System Overview Dashboard
- System health status
- Component availability
- Resource utilization (CPU, memory, disk)
- Network traffic
- Error rates and latencies

### Component-Specific Dashboards
- **Hermes Agent**: Session metrics, tool usage, response times
- **Neural Memory**: Memory operations, vector DB performance
- **PULSE**: API usage, data source performance
- **Jackrabbit**: Crypto operations, key management

### Business Metrics Dashboard
- User activity
- Feature usage
- Performance trends
- Capacity planning

## Alerting

### Alert Channels
```yaml
# alertmanager.yml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@hermes-stack.com'
  smtp_auth_username: 'alerts@hermes-stack.com'
  smtp_auth_password: '${SMTP_PASSWORD}'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'

receivers:
  - name: 'default'
    email_configs:
      - to: 'oncall@hermes-stack.com'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#alerts'
    discord_configs:
      - webhook_url: '${DISCORD_WEBHOOK_URL}'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_KEY}'
```

### Alert Severity Levels
- **Critical**: Immediate attention required (component down, data loss)
- **Warning**: Attention needed soon (high resource usage, performance degradation)
- **Info**: For awareness (config changes, maintenance events)

## Log Management

### Structured Logging
```python
# logger.py
import structlog
import logging

logger = structlog.get_logger()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Usage
logger.info("request_processed", 
           method="POST",
           endpoint="/api/chat",
           status=200,
           duration=0.123,
           user_id="user123")
```

### Log Queries
```bash
# Query logs from Loki
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={job="hermes-agent"} |= "error"' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2024-01-02T00:00:00Z' \
  --data-urlencode 'step=300'
```

## Distributed Tracing

### OpenTelemetry Setup
```python
# tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Set up tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

# Add span processor
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Instrument libraries
RequestsInstrumentor().instrument()

# Usage
with tracer.start_as_current_span("process_request") as span:
    span.set_attribute("user.id", "user123")
    span.set_attribute("request.type", "chat")
    # Process request...
```

## Performance Optimization

### Resource Allocation
```yaml
# docker-compose.override.yml
version: '3.8'
services:
  prometheus:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
  
  grafana:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
  
  loki:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
```

### Data Retention Policies
```yaml
# prometheus.yml
global:
  retention: 30d
  retention_size: 50GB

# loki-config.yml
limits_config:
  retention_period: 720h  # 30 days
  max_query_length: 721h
```

## Security Considerations

### Authentication & Authorization
- Grafana: LDAP/OAuth integration
- Prometheus: Basic auth or reverse proxy
- Network isolation: Internal Docker network
- TLS encryption for all endpoints

### Data Protection
- Log sanitization (remove sensitive data)
- Metrics aggregation (no PII)
- Access control per team
- Audit logging

## Troubleshooting

### Common Issues
1. **Metrics not appearing**
   - Check target health in Prometheus UI
   - Verify network connectivity
   - Check firewall rules

2. **High resource usage**
   - Reduce scrape frequency
   - Implement metric relabeling
   - Use recording rules

3. **Alert storms**
   - Adjust alert grouping
   - Implement inhibition rules
   - Set appropriate thresholds

### Debug Commands
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Loki health
curl http://localhost:3100/ready

# Test alert rules
curl -X POST http://localhost:9090/api/v1/rules

# View Grafana logs
docker logs grafana -f
```

## Integration with Hermes Components

### Hermes Agent Integration
```python
# Add to hermes-agent/main.py
from observability import setup_metrics, setup_tracing, setup_logging

# Initialize observability
setup_metrics(port=8000)
setup_tracing(service_name="hermes-agent")
setup_logging(service_name="hermes-agent")

# Add middleware for request tracking
@app.middleware("http")
async def observability_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response
```

## Support and Documentation
- GitHub: https://github.com/itsXactlY/hermes-stack-observability
- Documentation: https://github.com/itsXactlY/hermes-stack-observability/wiki
- Community: https://discord.gg/hermes-stack
- Grafana Docs: https://grafana.com/docs/
- Prometheus Docs: https://prometheus.io/docs/