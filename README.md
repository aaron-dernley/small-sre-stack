# Prima SRE Tech Challenge

A production-ready Python REST API backed by **DynamoDB** (user persistence)
and **S3** (avatar storage), fully containerised with Docker, provisioned with
**Terraform**, deployed via **Helm** on Kubernetes, and shipped with a GitHub
Actions CI/CD pipeline.

---

## Reviewer Quickstart

> **Prerequisites:** Docker, Docker Compose v2, Terraform ≥ 1.5, Python 3.11+
>
> No AWS account or real credentials are needed — everything runs against
> **LocalStack** using dummy credentials injected automatically.

```bash
# 1. Run unit tests (no services needed — all AWS calls are mocked)
make test

# 2. Start the full local stack in production order:
#    LocalStack → Terraform provisions infra → API starts
make dev

# 3. Verify the API end-to-end
make smoke-test

# 4. Tear down
make down
```

`make smoke-test` exercises all three endpoints and prints the responses:

```
── GET /health ──────────────────────────────────────────────
{"status": "healthy"}

── GET /users (before create) ───────────────────────────────
[]

── POST /user ───────────────────────────────────────────────
{
    "name": "Test User",
    "email": "test-user@prima.it",
    "avatar_url": "http://localhost:4566/prima-tech-challenge/avatars/<uuid>.png"
}

── GET /users (after create) ────────────────────────────────
[
    {
        "name": "Test User",
        "email": "test-user@prima.it",
        "avatar_url": "http://localhost:4566/prima-tech-challenge/avatars/<uuid>.png"
    }
]
```

All available Makefile targets:

```
make help
```

---

## Why `make dev` mirrors production

In production the deployment pipeline runs in this order:

```
terraform apply  →  infrastructure exists  →  application deployed
```

`make dev` enforces the same sequence locally:

1. Start LocalStack (emulates S3, DynamoDB, IAM)
2. Run `terraform apply` to provision the table, bucket, IAM role and policies
3. Start the API container — it boots against already-existing infrastructure

This avoids the anti-pattern of letting the application bootstrap its own
infrastructure, and ensures the local environment exercises the same dependency
graph as production.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Task 1 – Python API](#task-1--python-api)
4. [Task 2 – Docker](#task-2--docker)
5. [Task 3 – Terraform IaC](#task-3--terraform-iac)
6. [Task 4 – Kubernetes / Helm](#task-4--kubernetes--helm)
7. [Task 5 – CI/CD](#task-5--cicd)
8. [Production Considerations](#production-considerations)

---

## Architecture Overview

```
  ┌─────────────────────────────────────────────────────────┐
  │                   Kubernetes Cluster                    │
  │                                                         │
  │  ┌──────────┐  HPA   ┌──────────┐  ┌──────────┐       │
  │  │  Ingress │──────▶│ prima-api │  │ prima-api │ ...   │
  │  └──────────┘        │  pod     │  │  pod     │       │
  │                      └────┬─────┘  └────┬─────┘       │
  │                           │ IRSA         │              │
  └───────────────────────────┼─────────────┼──────────────┘
                              │             │
                     ┌────────▼──┐   ┌──────▼──────┐
                     │ DynamoDB  │   │     S3      │
                     │ (users)   │   │  (avatars)  │
                     └───────────┘   └─────────────┘
```

### Key Design Decisions

| Concern | Choice | Rationale |
|---|---|---|
| Framework | FastAPI | Async, type-safe, auto OpenAPI docs |
| AWS SDK | boto3 | Official, mature, supports LocalStack |
| IaC | Terraform | Wide adoption, modular, LocalStack-compatible |
| Auth (EKS) | IRSA | No long-lived credentials in pods |
| Autoscaling | HPA (CPU + Memory) | Handles traffic spikes automatically |
| Availability | PDB + podAntiAffinity | Survives node maintenance |
| Container security | non-root, read-only FS, dropped capabilities | Defence-in-depth |

---

## Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Docker | 24 | https://docs.docker.com/get-docker/ |
| Docker Compose | v2 | bundled with Docker Desktop |
| Terraform | 1.5 | `brew install hashicorp/tap/terraform` |
| Python | 3.11 | `brew install python` |
| Helm | 3.14 | `brew install helm` (Task 4 only) |
| kubectl | 1.28 | `brew install kubectl` (Task 4 only) |
| minikube | 1.32 | `brew install minikube` (Task 4 optional) |

---

## Task 1 – Python API

### Project structure

```
app/
├── config.py               # pydantic-settings — reads env vars
├── main.py                 # FastAPI application entry point
├── models/
│   └── user.py             # Pydantic request/response schemas
├── routes/
│   └── users.py            # GET /users  &  POST /user handlers
└── services/
    ├── dynamodb_service.py # DynamoDB put/scan operations
    └── s3_service.py       # S3 avatar upload
tests/
├── conftest.py             # moto fixtures — no real AWS needed
└── test_users_api.py       # 11 integration tests
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/users` | Return list of all users |
| `POST` | `/user` | Create user + upload avatar |
| `GET` | `/health` | Liveness health check |

**`POST /user`** accepts `multipart/form-data`:

| Field | Type | Notes |
|---|---|---|
| `name` | string | required |
| `email` | string | required, validated format |
| `avatar` | file | required, JPEG / PNG / GIF / WebP, ≤ 5 MB |

**`GET /users`** response:

```json
[
  {
    "name": "Test User",
    "email": "test-user@prima.it",
    "avatar_url": "https://prima-tech-challenge.s3.us-east-1.amazonaws.com/avatars/uuid.png"
  }
]
```

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `AWS_REGION` | `us-east-1` | AWS region |
| `DYNAMODB_TABLE_NAME` | `prima-tech-challenge-users` | DynamoDB table name |
| `S3_BUCKET_NAME` | `prima-tech-challenge` | S3 bucket name |
| `AWS_ENDPOINT_URL` | *(unset)* | Custom endpoint — set to LocalStack URL |
| `S3_PUBLIC_URL_BASE` | *(unset)* | Public URL prefix for avatar links |

---

## Task 2 – Docker

### Build

```bash
make build
# or directly:
docker build -t prima-api:local .
```

### Image hardening

- **Multi-stage build** — build dependencies never reach the production image
- **Virtual environment at `/venv`** — self-contained, no path ambiguity between build and run stages
- **Non-root user** (`appuser`, UID 1000) — limits blast radius if the process is compromised
- **Read-only root filesystem** — `/tmp` mounted as `emptyDir` for any transient writes
- **All Linux capabilities dropped** — only what uvicorn needs to serve HTTP
- **Built-in healthcheck** — uses Python's `urllib` so no extra tools (curl, wget) are needed in the image

---

## Task 3 – Terraform IaC

### Resources created (12 total)

| Resource | Description |
|---|---|
| `aws_s3_bucket` | Avatar storage |
| `aws_s3_bucket_versioning` | Versioning enabled |
| `aws_s3_bucket_server_side_encryption_configuration` | AES-256 SSE at rest |
| `aws_s3_bucket_public_access_block` | Controlled public read for avatar URLs |
| `aws_s3_bucket_policy` | Public `GetObject` for avatar serving |
| `aws_s3_bucket_lifecycle_configuration` | Expire old versions after 90 days |
| `aws_dynamodb_table` | User records, PAY_PER_REQUEST billing, PITR + SSE |
| `aws_iam_policy` × 2 | Least-privilege policies for S3 and DynamoDB |
| `aws_iam_role` | Workload identity — EC2 trust locally, IRSA on EKS |
| `aws_iam_role_policy_attachment` × 2 | Attach policies to role |

### Run via Makefile (recommended)

```bash
make dev   # runs terraform apply automatically as part of the stack
```

### Run manually against LocalStack

```bash
cd terraform
terraform init
terraform apply -var="localstack_endpoint=http://localhost:4566"
terraform output
```

### Run against real AWS

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — leave localstack_endpoint blank, set real values
terraform init
terraform plan
terraform apply
```

### IRSA setup (EKS)

After creating your EKS cluster:

```bash
aws eks describe-cluster --name <cluster-name> \
  --query "cluster.identity.oidc.issuer" --output text
```

Set in `terraform.tfvars`:

```hcl
eks_oidc_provider_arn    = "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/<OIDC_HOST>"
eks_oidc_provider_url    = "<OIDC_HOST>"
k8s_namespace            = "prima"
k8s_service_account_name = "prima-api"
```

Re-apply, then annotate the Helm values with the output role ARN:

```yaml
serviceAccount:
  annotations:
    eks.amazonaws.com/role-arn: "<output: api_iam_role_arn>"
```

---

## Task 4 – Kubernetes / Helm

### Chart structure

```
helm/prima-api/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl        # Named template helpers
    ├── configmap.yaml      # Non-secret env vars
    ├── deployment.yaml     # Deployment with hardened security context
    ├── hpa.yaml            # HorizontalPodAutoscaler (CPU + memory)
    ├── ingress.yaml        # Optional ingress
    ├── pdb.yaml            # PodDisruptionBudget
    ├── service.yaml        # ClusterIP service
    └── serviceaccount.yaml # ServiceAccount (IRSA-annotatable)
```

### Reliability features

| Feature | Default |
|---|---|
| HPA — min/max replicas | 2 / 10 |
| HPA — scale trigger | CPU > 70% or Memory > 80% |
| PodDisruptionBudget | `minAvailable: 1` |
| Pod anti-affinity | prefer different nodes |
| Liveness probe | `GET /health` every 30 s |
| Readiness probe | `GET /health` every 10 s |
| CPU / memory limits | 500m / 256Mi |
| Read-only root filesystem | enabled |
| Non-root UID | 1000 |
| Dropped capabilities | ALL |

### Deploy to minikube (optional local test)

```bash
minikube start

eval $(minikube docker-env)
docker build -t prima-api:local .

MINIKUBE_IP=$(minikube ip)

helm upgrade --install prima-api helm/prima-api/ \
  --set image.repository=prima-api \
  --set image.tag=local \
  --set image.pullPolicy=Never \
  --set replicaCount=1 \
  --set autoscaling.enabled=false \
  --set "env.AWS_ENDPOINT_URL=http://${MINIKUBE_IP}:4566" \
  --set "env.S3_PUBLIC_URL_BASE=http://${MINIKUBE_IP}:4566/prima-tech-challenge" \
  --set "env.AWS_ACCESS_KEY_ID=test" \
  --set "env.AWS_SECRET_ACCESS_KEY=test"

kubectl get pods -w
kubectl port-forward svc/prima-api 8080:80
curl http://localhost:8080/health
```

### Deploy to EKS

```bash
helm upgrade --install prima-api helm/prima-api/ \
  --namespace prima --create-namespace \
  --set image.repository=ghcr.io/your-org/prima-api \
  --set image.tag=sha-<commit> \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=<ROLE_ARN>
```

---

## Task 5 – CI/CD

Pipeline: `.github/workflows/ci-cd.yaml`

### Job graph

```
test (3.11 + 3.12) ───────────────────────────────────────────┐
lint (ruff) ───────────────────────────────────────────────────┤
security-python (bandit) ──────────────────────────────────────┼──▶ build ──▶ scan-image (trivy)
terraform-validate ────────────────────────────────────────────┤
helm-lint ─────────────────────────────────────────────────────┘
```

| Job | Tool | What it checks |
|---|---|---|
| `test` | pytest + moto | All API logic, mocked AWS, Python 3.11 + 3.12 matrix |
| `lint` | ruff | Style, imports, formatting |
| `security-python` | Bandit | Common Python security issues (SAST) |
| `terraform-validate` | Terraform CLI | HCL formatting + schema validation |
| `helm-lint` | Helm | Chart structure + dry-run render |
| `build` | Docker Buildx | Image push to GHCR with SBOM + provenance |
| `scan-image` | Trivy | CVE scan → GitHub Security SARIF |

All five quality gates must pass before `build` runs. Images are only pushed
on commits to `main` — PRs build but do not push, so fork PRs never touch
registry credentials.

---

## Production Considerations

| Topic | Production approach |
|---|---|
| **Avatar URLs** | Replace public bucket with server-side **pre-signed URLs** (time-limited, no public bucket exposure) |
| **Credentials** | Use IRSA — no static `AWS_*` env vars in pods at all |
| **TLS** | Terminate at ingress via cert-manager + Let's Encrypt or ACM |
| **Observability** | Structured JSON logs, Prometheus metrics (`/metrics`), OpenTelemetry traces |
| **Rate limiting** | FastAPI middleware (e.g. `slowapi`) to prevent abuse |
| **DynamoDB pagination** | Replace `scan` with paginated requests for large datasets |
| **Terraform state** | S3 backend + DynamoDB state lock table for concurrent team use |
| **Multi-region** | DynamoDB Global Tables + S3 Cross-Region Replication |
| **Image registry** | Private ECR with immutability + scan-on-push enabled |
