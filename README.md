# Prima SRE Tech Challenge

Python REST API backed by DynamoDB and S3, containerised with Docker, provisioned with Terraform, deployed via Helm on Kubernetes, with a GitHub Actions CI/CD pipeline.

---

## Quickstart

**Prerequisites:** Docker, Docker Compose v2, Terraform ≥ 1.5, Python 3.9+

No AWS account needed — everything runs against LocalStack with dummy credentials.

```bash
# Install Python test dependencies
# On Ubuntu 23.04+ you may need a venv or --break-system-packages
pip3 install -r requirements-dev.txt

# Run unit tests (no services required — AWS calls are mocked with moto)
make test

# Start the full local stack
# LocalStack → terraform apply → API
make dev

# Smoke test all three endpoints
make smoke-test

# Tear down
make down
```

`make smoke-test` output:

```
── GET /health ──────────────────────────────────────────────
{
    "status": "healthy"
}

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

```bash
# All available targets
make help
```

`make dev` mirrors the production deployment order — Terraform provisions infrastructure first, then the application starts against it. The application never bootstraps its own infrastructure.

---

## Task 1 – Python API

### Structure

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
└── test_users_api.py       # 12 tests
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/users` | List all users |
| `POST` | `/user` | Create user + upload avatar |
| `GET` | `/health` | Health check |

**`POST /user`** — `multipart/form-data`:

| Field | Type | Notes |
|---|---|---|
| `name` | string | required |
| `email` | string | required, validated |
| `avatar` | file | required, JPEG / PNG / GIF / WebP, ≤ 5 MB |

### Configuration

| Variable | Default | Description |
|---|---|---|
| `AWS_REGION` | `us-east-1` | AWS region |
| `DYNAMODB_TABLE_NAME` | `prima-tech-challenge-users` | DynamoDB table |
| `S3_BUCKET_NAME` | `prima-tech-challenge` | S3 bucket |
| `AWS_ENDPOINT_URL` | *(unset)* | Set to LocalStack URL for local dev |
| `S3_PUBLIC_URL_BASE` | *(unset)* | Public URL prefix for avatar links |

---

## Task 2 – Docker

```bash
make build
```

- Multi-stage build — build dependencies don't reach the production image
- Virtual environment at `/venv` — isolated from the system Python
- Non-root user (`appuser`, UID 1000)
- Read-only root filesystem
- All Linux capabilities dropped
- Healthcheck via Python's `urllib` — no curl or wget needed in the image

---

## Task 3 – Terraform IaC

11 resources across S3, DynamoDB, and IAM:

| Resource | Notes |
|---|---|
| `aws_s3_bucket` | Avatar storage |
| `aws_s3_bucket_versioning` | Enabled |
| `aws_s3_bucket_server_side_encryption_configuration` | AES-256 |
| `aws_s3_bucket_public_access_block` | Allows public reads for avatar URLs |
| `aws_s3_bucket_policy` | Public `GetObject` |
| `aws_dynamodb_table` | PAY_PER_REQUEST, PITR enabled |
| `aws_iam_policy` × 2 | Least-privilege S3 and DynamoDB policies |
| `aws_iam_role` | EC2 trust policy locally; IRSA on EKS |
| `aws_iam_role_policy_attachment` × 2 | Attach policies to role |

### Run manually against LocalStack

```bash
cd terraform
terraform init
terraform apply -var="localstack_endpoint=http://localhost:4566"
terraform output
```

### Run against real AWS

Edit `terraform/terraform.tfvars` — comment out `localstack_endpoint` and fill in your region/project values, then:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### IRSA setup (EKS)

After creating your EKS cluster, get the OIDC issuer:

```bash
aws eks describe-cluster --name <cluster-name> \
  --query "cluster.identity.oidc.issuer" --output text
```

Set in `terraform/terraform.tfvars`:

```hcl
eks_oidc_provider_arn    = "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/<OIDC_HOST>"
eks_oidc_provider_url    = "<OIDC_HOST>"
k8s_namespace            = "prima"
k8s_service_account_name = "prima-api"
```

Re-apply, then annotate the service account in Helm values with the output role ARN:

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

| Feature | Value |
|---|---|
| HPA replicas | min 2 / max 10 |
| HPA triggers | CPU > 70% or Memory > 80% |
| PodDisruptionBudget | `minAvailable: 1` |
| Pod anti-affinity | prefer different nodes |
| Liveness probe | `GET /health` every 30 s |
| Readiness probe | `GET /health` every 10 s |
| CPU / memory limits | 500m / 256Mi |
| Root filesystem | read-only |
| UID | 1000 (non-root) |
| Capabilities | ALL dropped |

### Deploy to minikube

**Prerequisites:** minikube, helm, kubectl

`make dev` must be running first (LocalStack needs to be up for the pods to reach it).

```bash
make k8s
```

This runs four steps in order: start minikube → build and load the image → deploy the Helm chart → port-forward and smoke test. The pods reach LocalStack via `host.minikube.internal:4566`.

To tear down:

```bash
make k8s-down
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

```
test ──────────────────────────────────────────────────────────┐
lint (ruff) ───────────────────────────────────────────────────┤
security-python (bandit) ──────────────────────────────────────┼──▶ build ──▶ scan-image (trivy)
terraform-validate ────────────────────────────────────────────┤
helm-lint ─────────────────────────────────────────────────────┘
```

| Job | Tool | Checks |
|---|---|---|
| `test` | pytest + moto | All API logic, mocked AWS |
| `lint` | ruff | Style, imports, formatting |
| `security-python` | bandit | SAST — common Python security issues |
| `terraform-validate` | Terraform CLI | HCL formatting + schema validation |
| `helm-lint` | Helm | Chart structure + dry-run render |
| `build` | Docker Buildx | Image push to GHCR with SBOM + provenance |
| `scan-image` | Trivy | CVE scan — CRITICAL/HIGH findings logged to job output |

All five quality gates must pass before `build` runs. Images are only pushed on commits to `main` — PRs build but do not push.

### What the pipeline would look like in a production team

**Pull request gates**

The pipeline already runs all five quality checks (test, lint, SAST, terraform-validate, helm-lint) on every PR. What's missing is enforcement — currently nothing stops a PR being merged if those checks fail. In production you would pair this with GitHub branch protection rules that mark those jobs as required status checks. A PR with a failing test, lint error, or security finding cannot be merged until it is fixed. The build and image push jobs deliberately don't run on PRs (no point pushing an unreviewed image), but all the validation that protects `main` runs on every commit to every branch.

**Versioning**

The current image tagging strategy uses the branch name (`main`) and commit SHA (`sha-abc1234`). In a release workflow you would adopt semantic versioning — patch bumps for fixes, minor for new features, major for breaking changes. Tags like `v1.4.2` would be created either manually or via a tool like `semantic-release`, which reads conventional commit messages (`fix:`, `feat:`, `feat!:`) and determines the next version automatically. The same SHA-tagged image built in CI gets re-tagged with the semver version at promotion time — no rebuild. This gives every running deployment a human-readable version that maps directly to a git tag, a changelog entry, and a known set of changes.

**Artifact management**

GHCR works for a single-team project, but a larger organisation would typically use a dedicated artifact repository like JFrog Artifactory or AWS ECR with replication. Artifactory gives you a single registry for Docker images, Helm charts, Python packages, and Terraform modules, with fine-grained access control, retention policies, and audit logs across all of them. It also proxies public registries (PyPI, Docker Hub) so your builds don't depend on external uptime and every dependency pulled in CI is cached and scanned internally.

**Image promotion**

Rather than building a new image on every merge to `main`, a mature pipeline promotes a single immutable image through environments. The image built and scanned from a PR is tagged with its commit SHA — that exact image (not a rebuild) is what gets deployed to staging and then production. This guarantees what was tested is what ships.

**Secrets management**

Static secrets in GitHub Actions are a starting point. In production these would be replaced with short-lived credentials via OIDC federation — GitHub Actions already supports this for AWS, so the pipeline can assume an IAM role directly without storing any AWS keys as secrets at all.

**End-to-end / integration tests**

The current test suite mocks AWS with moto. A production pipeline would add a stage that deploys to a short-lived staging environment, runs integration tests against it (real DynamoDB, real S3), and tears it down — giving confidence that the infrastructure and application work together, not just in isolation.

**Deployment**

The pipeline currently stops at building and scanning the image. The natural next step is a deploy job that runs `helm upgrade` against a staging cluster on every merge to `main`, gated behind the full quality pipeline. Production promotion could be a separate manual-approval job or triggered by tagging a release.

---

## Production considerations

| Topic | Approach |
|---|---|
| Avatar URLs | Pre-signed URLs (time-limited, no public bucket) |
| Credentials | IRSA — no static `AWS_*` env vars in pods |
| TLS | Terminate at ingress via cert-manager + ACM |
| Observability | Structured JSON logs, Prometheus `/metrics`, OpenTelemetry traces |
| Rate limiting | `slowapi` middleware |
| DynamoDB pagination | Replace `scan` with paginated queries for large datasets |
| Terraform state | S3 backend + DynamoDB lock table |
| Multi-region | DynamoDB Global Tables + S3 Cross-Region Replication |
| Image registry | Private ECR or Artifactory with immutability + scan-on-push |
