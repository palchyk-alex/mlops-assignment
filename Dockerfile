# Container for the agent's FastAPI server only (agent/server.py).
#
# vLLM, Prometheus/Grafana and Langfuse are not part of this image - they
# keep running on the host / via docker-compose, and this container reaches
# them over the network (see VLLM_BASE_URL / LANGFUSE_HOST below).
#
# Build:
#   docker build -t mlops-agent:local .
#
# Run standalone (for a smoke test outside k8s):
#   docker run --rm -p 8001:8001 \
#     -e VLLM_BASE_URL=http://host.docker.internal:8000/v1 \
#     mlops-agent:local
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VLLM_BASE_URL=http://host.minikube.internal:8000/v1 \
    VLLM_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507 \
    LANGFUSE_HOST=http://host.minikube.internal:3001

# Only the agent's runtime deps - deliberately not the full project
# dependency set (vllm/torch/datasets are unrelated to serving this API).
RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.0,<3.0" \
    "python-dotenv>=1.0,<2.0" \
    "langgraph>=1.0,<2.0" \
    "langchain>=1.0,<2.0" \
    "langchain-openai>=1.0,<2.0" \
    "langfuse>=4.0,<5.0"

COPY agent/ ./agent/
# Bundled so the agent can run standalone in minikube with no extra mounts.
# .dockerignore trims this down to just the top-level *.sqlite files.
COPY data/bird/ ./data/bird/

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

CMD ["uvicorn", "agent.server:app", "--host", "0.0.0.0", "--port", "8001"]
