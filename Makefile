.PHONY: help dev test test-cov build smoke-test load down clean logs logs-api logs-localstack \
        tf-apply tf-destroy \
        k8s k8s-start k8s-build k8s-deploy k8s-test k8s-down \
        observability

SHELL       := /bin/bash
PROJECT_DIR := $(shell pwd)
TF_DIR      := $(PROJECT_DIR)/terraform
HELM_RELEASE := prima-api
HELM_CHART   := helm/prima-api
K8S_PORT     := 8080

# LocalStack endpoint used by Terraform (passed as -var so no tfvars editing needed)
LOCALSTACK_ENDPOINT := http://localhost:4566

# ── Default target ────────────────────────────────────────────────────────────

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Primary workflow (mirrors production order) ───────────────────────────────

dev: ## Full demo: LocalStack → Terraform → API + Observability → Kubernetes
	@echo ""
	@echo "==> Checking prerequisites..."
	@command -v minikube >/dev/null 2>&1 || { echo "ERROR: minikube not found — https://minikube.sigs.k8s.io/docs/start/"; exit 1; }
	@command -v helm     >/dev/null 2>&1 || { echo "ERROR: helm not found — https://helm.sh/docs/intro/install/"; exit 1; }
	@command -v kubectl  >/dev/null 2>&1 || { echo "ERROR: kubectl not found — https://kubernetes.io/docs/tasks/tools/"; exit 1; }
	@echo "    minikube, helm, kubectl — OK"
	@echo ""
	@echo "==> [1/4] Starting LocalStack..."
	@docker compose up localstack -d
	@echo "==> Waiting for LocalStack to be ready..."
	@until curl -sf $(LOCALSTACK_ENDPOINT)/_localstack/health > /dev/null 2>&1; do \
		printf "."; sleep 2; \
	done
	@echo " ready."
	@echo ""
	@echo "==> [2/4] Provisioning infrastructure with Terraform..."
	@$(MAKE) tf-apply
	@echo ""
	@echo "==> [3/4] Starting API + observability stack..."
	@docker compose up api prometheus grafana -d
	@echo "==> Waiting for API to be healthy..."
	@until curl -sf http://localhost:8000/health > /dev/null 2>&1; do \
		printf "."; sleep 2; \
	done
	@echo " ready."
	@echo ""
	@echo "==> [4/4] Deploying to Kubernetes (minikube + Helm)..."
	@$(MAKE) k8s
	@echo "==> Starting persistent port-forward svc/$(HELM_RELEASE) → localhost:$(K8S_PORT)..."
	@kubectl port-forward svc/$(HELM_RELEASE) $(K8S_PORT):80 >/dev/null 2>&1 & echo $$! > .k8s-pf.pid
	@sleep 2
	@echo ""
	@echo "------------------------------------------------------------"
	@echo "  Stack is up:"
	@echo ""
	@echo "  docker-compose:"
	@echo "    API (direct):  http://localhost:8000"
	@echo "    API docs:      http://localhost:8000/docs"
	@echo "    Metrics:       http://localhost:8000/metrics"
	@echo "    Prometheus:    http://localhost:9090"
	@echo "    Grafana:       http://localhost:3000  (no login required)"
	@echo ""
	@echo "  Kubernetes (Helm chart on minikube):"
	@echo "    API (k8s):     http://localhost:$(K8S_PORT)"
	@echo "    API docs (k8s): http://localhost:$(K8S_PORT)/docs"
	@echo ""
	@echo "  Next steps:"
	@echo "    make smoke-test   # verify the API (docker-compose)"
	@echo "    make load         # send traffic and populate Grafana"
	@echo "    make down         # stop everything"
	@echo "------------------------------------------------------------"
	@echo ""

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run unit tests (no running services needed — uses moto mocks)
	@echo "==> Running unit tests..."
	@python3 -m pytest tests/ -v --tb=short

test-cov: ## Run unit tests with coverage report
	@python3 -m pytest tests/ -v --cov=app --cov-report=term-missing

smoke-test: ## Run API smoke tests against the running local stack (port 8000)
	@$(MAKE) _smoke PORT=8000

load: ## Send 60 s of mixed traffic to populate the Grafana dashboard (DURATION=N to override)
	@python3 scripts/load.py --url http://localhost:8000 --duration $${DURATION:-60}

k8s-smoke-test: ## Run API smoke tests against the k8s deployment (port 8080)
	@$(MAKE) _smoke PORT=$(K8S_PORT)

# Internal target — shared smoke test logic, called with PORT=xxxx
_smoke:
	@echo ""
	@python3 -c "import base64; open('/tmp/prima-test-avatar.png', 'wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=='))"
	@echo "── GET /health ──────────────────────────────────────────────"
	@curl -sf http://localhost:$(PORT)/health | python3 -m json.tool
	@echo ""
	@echo "── GET /users (before create) ───────────────────────────────"
	@curl -sf http://localhost:$(PORT)/users | python3 -m json.tool
	@echo ""
	@echo "── POST /user ───────────────────────────────────────────────"
	@curl -sf -X POST http://localhost:$(PORT)/user \
		-F "name=Test User" \
		-F "email=test-user@prima.it" \
		-F "avatar=@/tmp/prima-test-avatar.png;type=image/png" \
		| python3 -m json.tool
	@echo ""
	@echo "── GET /users (after create) ────────────────────────────────"
	@curl -sf http://localhost:$(PORT)/users | python3 -m json.tool
	@echo ""

# ── Docker ────────────────────────────────────────────────────────────────────

build: ## Build the Docker image
	@docker build -t prima-api:local .

# ── Terraform ─────────────────────────────────────────────────────────────────

tf-apply: ## Provision infrastructure in LocalStack via Terraform
	@if [ ! -d "$(TF_DIR)/.terraform" ]; then \
		echo "==> Initialising Terraform..."; \
		cd $(TF_DIR) && terraform init -input=false; \
	fi
	@cd $(TF_DIR) && terraform apply -auto-approve \
		-var="localstack_endpoint=$(LOCALSTACK_ENDPOINT)"

tf-destroy: ## Destroy Terraform-managed resources in LocalStack
	@cd $(TF_DIR) && terraform destroy -auto-approve \
		-var="localstack_endpoint=$(LOCALSTACK_ENDPOINT)"

# ── Kubernetes (minikube) ─────────────────────────────────────────────────────
#
# LocalStack runs on the host via docker compose.
# Pods reach it via host.minikube.internal (minikube's DNS alias for the host).
# Avatar URLs in API responses use localhost:4566 so they work in the browser.

k8s: k8s-start k8s-build k8s-deploy k8s-test ## Full k8s workflow: start → build → deploy → test

k8s-start: ## Start minikube
	@echo "==> Starting minikube..."
	@minikube start
	@echo "==> minikube ready."

k8s-build: ## Build image on host and load it into minikube
	@echo "==> Building image..."
	@docker build -t prima-api:local .
	@echo "==> Loading image into minikube..."
	@minikube image load prima-api:local
	@echo "==> Image loaded."

k8s-deploy: ## Deploy Helm chart to minikube
	@echo "==> Deploying via Helm..."
	@helm upgrade --install $(HELM_RELEASE) $(HELM_CHART)/ \
		--set image.repository=prima-api \
		--set image.tag=local \
		--set image.pullPolicy=Never \
		--set replicaCount=1 \
		--set autoscaling.enabled=false \
		--set "env.AWS_ENDPOINT_URL=http://host.minikube.internal:4566" \
		--set "env.S3_PUBLIC_URL_BASE=http://localhost:4566/prima-tech-challenge" \
		--set "env.AWS_ACCESS_KEY_ID=test" \
		--set "env.AWS_SECRET_ACCESS_KEY=test"
	@echo "==> Waiting for deployment to be ready..."
	@kubectl rollout status deployment/$(HELM_RELEASE) --timeout=120s

k8s-test: ## Port-forward and smoke test the k8s deployment
	@echo "==> Port-forwarding svc/$(HELM_RELEASE) → localhost:$(K8S_PORT)..."
	@kubectl port-forward svc/$(HELM_RELEASE) $(K8S_PORT):80 & \
	PF_PID=$$!; \
	sleep 3; \
	$(MAKE) _smoke PORT=$(K8S_PORT); \
	kill $$PF_PID 2>/dev/null; \
	wait $$PF_PID 2>/dev/null; true

k8s-down: ## Uninstall Helm release and stop minikube
	@echo "==> Uninstalling Helm release..."
	@helm uninstall $(HELM_RELEASE) 2>/dev/null || true
	@echo "==> Stopping minikube..."
	@minikube stop
	@echo "==> Done."

# ── Teardown ──────────────────────────────────────────────────────────────────

down: ## Stop all services — docker-compose, Kubernetes port-forward, and minikube
	@echo "==> Stopping Kubernetes port-forward..."
	@if [ -f .k8s-pf.pid ]; then \
		kill $$(cat .k8s-pf.pid) 2>/dev/null || true; \
		rm -f .k8s-pf.pid; \
	fi
	@echo "==> Stopping minikube..."
	@minikube status 2>/dev/null | grep -q "Running" && $(MAKE) k8s-down || true
	@echo "==> Stopping docker-compose..."
	@docker compose down

clean: ## Stop all services and remove local Terraform state
	@$(MAKE) down
	@rm -f  $(TF_DIR)/terraform.tfstate $(TF_DIR)/terraform.tfstate.backup
	@rm -rf $(TF_DIR)/.terraform $(TF_DIR)/.terraform.lock.hcl
	@echo "==> Clean complete."

# ── Observability ─────────────────────────────────────────────────────────────

observability: ## Open Grafana and Prometheus in the browser
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3000"
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || true

# ── Logs ──────────────────────────────────────────────────────────────────────

logs: ## Tail logs from all services
	@docker compose logs -f

logs-api: ## Tail API logs only
	@docker compose logs -f api

logs-localstack: ## Tail LocalStack logs only
	@docker compose logs -f localstack
