# CI Load Test for Kubernetes

> **Goodnotes Senior DevOps Take-Home Assignment**  
> Automated CI pipeline for load testing Kubernetes ingress routing with randomised traffic distribution

## Overview

This project implements a GitHub Actions workflow that provisions a local multi-node Kubernetes cluster using kind, deploys HTTP echo deployments and services with ingress routing, executes randomised load tests, and posts performance metrics as PR comments.

**Time Taken:** ~4 hours

## Architecture

```
GitHub Actions Runner (Ubuntu)
├── Kind Cluster (3 nodes: 1 control-plane + 2 workers)
│   ├── nginx-ingress-controller (ingress-nginx namespace)
│   └── ci-load-test namespace
│       ├── foo deployment (hashicorp/http-echo)
│       ├── bar deployment (hashicorp/http-echo)
│       ├── Services (foo:80, bar:80)
│       └── Ingress (foo.localhost → foo, bar.localhost → bar)
└── k6 Load Tester → localhost:8080 (mapped to cluster)
```

## Components

### 1. Kubernetes Manifests (`k8s/`)

- **kind-config.yaml**: 3-node cluster with port mapping (80→8080, 443→443)
- **foo-deployment.yaml**: http-echo deployment responding with "foo"
- **bar-deployment.yaml**: http-echo deployment responding with "bar"
- **ingress.yaml**: nginx ingress routing for foo.localhost and bar.localhost

### 2. Load Test Scripts (`scripts/`)

- **loadtest.js**: k6 script with 20 VUs over 30s, randomized 50/50 traffic split
- **format-report.py**: Parses k6 JSON summary and generates markdown report

### 3. CI Workflow (`.github/workflows/load-test-ci.yaml`)

Orchestrates 10 steps:

1. Install kubectl + Kind
2. Provision multi-node cluster
3. Install nginx ingress controller with readiness checks
4. Verify IngressClass availability
5. Deploy foo/bar workloads
6. Wait for deployment readiness
7. Execute load tests (endpoint + routing validation)
8. Install k6
9. Run randomized load test
10. Post formatted metrics to PR comment

## Key Decisions

### Tool Selection

- **Kind**: Lightweight, CI-friendly Kubernetes distribution
- **nginx-ingress**: Industry-standard, well-supported in Kind
- **k6**: Modern load testing tool with native JSON export and scripting
- **Python**: Simple metric parsing without external dependencies

### Design Choices

1. **Multi-stage readiness validation**: Prevents race conditions between controller deployment and ingress admission
2. **Explicit namespace flags**: Avoids context-switching pitfalls in CI
3. **Port 8080 mapping**: GitHub Actions runners require non-privileged ports so had to use 8080
4. **Retry logic in load tests**: Handles eventual consistency in ingress backend sync

## Challenges & Solutions

### Challenge 1: Ingress Admission Webhook Race Condition

**Problem**: Applying ingress resources failed with webhook connection errors  
**Root Cause**: Webhook service endpoints not ready despite job completion  
**Solution**: Added explicit endpoint polling loop before proceeding to workload deployment

### Challenge 2: Port 80 Bind Failure on CI Runner

**Problem**: `curl localhost:80` returned "Connection refused"  
**Root Cause**: GitHub Actions runners don't allow privileged port binding  
**Solution**: Reverted to port 8080 mapping (Kind container:80 → host:8080)

### Challenge 3: 404 Errors During load Tests

**Problem**: Ingress returned 404 immediately after resource creation  
**Root Cause**: nginx controller needs time to sync backend endpoints  
**Solution**: Implemented service endpoint wait + 10-attempt retry loop with 2s intervals

### Challenge 4: Load Test Metrics Extraction

**Problem**: k6 console output is human-readable but hard to parse  
**Solution**: Used `--summary-export=summary.json` flag with Python parser for structured metric extraction

### Challenge 5: Ingress Controller Pod Scheduling Failure

**Problem**: Ingress controller pods remained in Pending state, causing wait commands to timeout  
**Root Cause**: nginx-ingress-controller uses nodeSelector requiring `ingress-ready=true` label  
**Solution**: Added `kubectl label node load-test-cluster-control-plane ingress-ready=true` before applying ingress controller manifest

## Metrics Reported

The CI pipeline posts these metrics as PR comments:

- **Throughput**: Requests per second
- **Reliability**: HTTP failure rate (%)
- **Latency**: Average, p90, p95 (milliseconds)

Sample thresholds enforced:

- HTTP error rate < 1%
- Status code 200 validation on all requests

## Running Locally

### Prerequisites

- Docker Desktop or Podman
- kubectl installed
- Kind installed

### Steps

```bash
# 1. Create cluster
kind create cluster --name load-test-cluster --config k8s/kind-config.yaml

# 2. Label control-plane node
kubectl label node load-test-cluster-control-plane ingress-ready=true

# 3. Install ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/kind/deploy.yaml

# 4. Wait for ingress controller
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# 5. Deploy workloads
kubectl create namespace ci-load-test
kubectl apply -f k8s/foo-deployment.yaml -f k8s/bar-deployment.yaml -f k8s/ingress.yaml -n ci-load-test

# 6. Wait for deployments
kubectl wait --for=condition=available --timeout=120s deployment/foo -n ci-load-test
kubectl wait --for=condition=available --timeout=120s deployment/bar -n ci-load-test

# 7. Test routing
curl -H "Host: foo.localhost" http://localhost:8080/  # Should return "foo"
curl -H "Host: bar.localhost" http://localhost:8080/  # Should return "bar"

# 8. Run load test (requires k6)
k6 run --summary-export=summary.json scripts/loadtest.js

# 9. Format report
python3 scripts/format-report.py

# 10. Cleanup
kind delete cluster --name load-test-cluster
```

## CI Workflow Execution

Workflow triggers automatically on pull requests to `main` branch.

## Improvements & Stretch Goals

### Implemented

- ✅ Graceful failure handling (timeouts, retries, exit codes)
- ✅ Declarative resources (pure YAML manifests)
- ✅ Progress validation at each step
- ✅ Clear, atomic commit history

### Future Enhancements

- **Monitoring**: Deploy Prometheus + Grafana for resource utilization metrics
  - Track CPU/memory during load test
  - Correlate application latency with resource saturation
  - Export node/pod metrics alongside k6 results
- **Templating**: Use Kustomize or Helm to reduce YAML duplication
- **Multi-region**: Test cross-AZ ingress routing patterns
- **Canary**: A/B test load distribution with weighted routing

## Tech Stack Summary

| Component    | Tool                 | Justification                                    |
| ------------ | -------------------- | ------------------------------------------------ |
| CI/CD        | GitHub Actions       | Native GitHub integration, free for public repos |
| Kubernetes   | Kind v0.31.0         | Lightweight, fast cluster provisioning in CI     |
| Ingress      | nginx-ingress v1.8.1 | Production-grade, Kind-optimized manifest        |
| Load Testing | k6 (Grafana)         | Modern, scriptable, excellent JSON export        |
| Scripting    | Bash + Python 3      | Minimal dependencies, CI runner pre-installed    |
| Manifests    | YAML                 | Declarative, version-controlled, auditable       |

## Repository Structure

```
.
├── .github/
│   └── workflows/
│       └── load-test-ci.yaml    # Main CI pipeline
├── k8s/
│   ├── kind-config.yaml         # Cluster configuration
│   ├── foo-deployment.yaml      # Foo service + deployment
│   ├── bar-deployment.yaml      # Bar service + deployment
│   └── ingress.yaml             # Ingress routing rules
├── scripts/
│   ├── loadtest.js              # k6 load test script
│   └── format-report.py         # Metrics formatter
└── README.md                    # This file
```

## Sample PR Execution

View the complete CI workflow execution with automated load test results:
**[Pull Request #1](https://github.com/isrealei/goodNotes-ci-load-test/pull/1)**

**Author**: Isreal Urephu  
**Assignment**: Goodnotes DevOps Engineer Take-Home Challenge  
**Completion Date**: 22nd of December, 2025
