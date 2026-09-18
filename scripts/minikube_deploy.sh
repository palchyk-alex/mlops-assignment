#!/usr/bin/env bash
# Build the agent image locally and deploy it to a running minikube cluster.
# Image is loaded straight into minikube's local image store - nothing is
# ever pushed to a registry, and the Deployment uses imagePullPolicy: Never.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

IMAGE="mlops-agent:local"

echo "==> Building $IMAGE"
docker build -t "$IMAGE" .

echo "==> Loading $IMAGE into minikube"
minikube image load "$IMAGE"

echo "==> Applying config"
kubectl apply -f k8s/configmap.yaml

if ! kubectl get secret agent-secrets >/dev/null 2>&1; then
  if [[ -f .env ]]; then
    echo "==> Creating agent-secrets from .env"
    kubectl create secret generic agent-secrets --from-env-file=.env
  else
    echo "==> No .env found and no agent-secrets secret exists yet."
    echo "    Create one first, e.g.:"
    echo "      kubectl create secret generic agent-secrets --from-literal=LANGFUSE_PUBLIC_KEY=... --from-literal=LANGFUSE_SECRET_KEY=..."
    exit 1
  fi
fi

echo "==> Applying deployment + service"
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml

echo "==> Waiting for rollout"
kubectl rollout status deployment/agent

echo "==> Done. Access it with:"
echo "    minikube service agent --url"
