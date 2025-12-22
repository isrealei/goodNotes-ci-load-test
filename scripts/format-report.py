import json

SUMMARY_FILE = "summary.json"
OUTPUT_FILE = "report.md"

with open(SUMMARY_FILE, "r") as f:
    data = json.load(f)

metrics = data.get("metrics", {})

def get_metric(metric, key, default=0):
    return metrics.get(metric, {}).get(key, default)

# Latency metrics (milliseconds)
avg = get_metric("http_req_duration", "avg")
p90 = get_metric("http_req_duration", "p(90)")
p95 = get_metric("http_req_duration", "p(95)")

# Throughput and errors
rps = get_metric("http_reqs", "rate")
fail_rate = get_metric("http_req_failed", "rate") * 100

report = f"""## CI Load Test Results

### Throughput & Reliability
- **Requests/sec:** {rps:.2f}
- **Failure rate:** {fail_rate:.2f}%

### Latency (ms)
- **Average:** {avg:.2f}
- **p90:** {p90:.2f}
- **p95:** {p95:.2f}

<sub>Generated automatically by k6 during CI</sub>
"""

with open(OUTPUT_FILE, "w") as f:
    f.write(report)

print(report)
