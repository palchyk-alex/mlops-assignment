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
kubectl apply -f k8s/secret.yaml

echo "==> Applying deployment + service"
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
