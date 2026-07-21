#!/bin/bash
# GCE startup script — rendered by Terraform templatefile().
# Runs once at instance boot; logs to GCE serial console.
set -euo pipefail

MODEL_ID="${model_id}"
MODEL_REVISION="${model_revision}"
HF_TOKEN="${hf_token}"
VLLM_VERSION="${vllm_version}"
LOCAL_MODEL_DIR="/model"

echo "[startup] model_id=$MODEL_ID revision=$MODEL_REVISION vllm=$VLLM_VERSION"

# Set HuggingFace token if provided (needed for gated models)
if [ -n "$HF_TOKEN" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

mkdir -p "$LOCAL_MODEL_DIR"

pip install -q "huggingface_hub[cli]"
huggingface-cli download "$MODEL_ID" \
  --revision "$MODEL_REVISION" \
  --local-dir "$LOCAL_MODEL_DIR" \
  --local-dir-use-symlinks False

# Start vLLM (Docker is pre-installed on the Deep Learning VM image)
echo "[startup] starting vLLM $VLLM_VERSION"
docker run -d \
  --name vllm-server \
  --restart unless-stopped \
  --gpus all \
  -v "$LOCAL_MODEL_DIR:/model" \
  -p 8000:8000 \
  "vllm/vllm-openai:$VLLM_VERSION" \
  --model /model \
  --served-model-name "$MODEL_ID" \
  --host 0.0.0.0 \
  --port 8000

# Health-gate: poll until vLLM is ready, with a 5-minute timeout.
echo "[startup] waiting for vLLM to become ready..."
MAX_WAIT=300
WAITED=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  sleep 5
  WAITED=$((WAITED + 5))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[startup] ERROR: vLLM did not become ready after $${MAX_WAIT}s — last container logs:"
    docker logs vllm-server 2>&1 | tail -30
    exit 1
  fi
done
echo "[startup] vLLM ready at http://localhost:8000/v1"
