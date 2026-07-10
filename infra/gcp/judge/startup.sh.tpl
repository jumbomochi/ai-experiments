#!/bin/bash
# GCE startup script — rendered by Terraform templatefile().
# Runs once at instance boot; logs to GCE serial console.
set -euo pipefail

MODEL_ID="${model_id}"
MODEL_REVISION="${model_revision}"
BUCKET="${bucket_name}"
HF_TOKEN="${hf_token}"
VLLM_VERSION="${vllm_version}"
LOCAL_MODEL_DIR="/model"
SENTINEL="gs://$BUCKET/$MODEL_ID/.cache_complete"

echo "[startup] model_id=$MODEL_ID revision=$MODEL_REVISION bucket=$BUCKET vllm=$VLLM_VERSION"

if [ -n "$HF_TOKEN" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

mkdir -p "$LOCAL_MODEL_DIR"

if gsutil -q stat "$SENTINEL" 2>/dev/null; then
  echo "[startup] cache hit — syncing from gs://$BUCKET/$MODEL_ID/"
  gsutil -m rsync -r "gs://$BUCKET/$MODEL_ID/" "$LOCAL_MODEL_DIR/"
else
  echo "[startup] cache miss — pulling from HuggingFace (72B AWQ ~45 min)"
  pip install -q "huggingface_hub[cli]"
  huggingface-cli download "$MODEL_ID" \
    --revision "$MODEL_REVISION" \
    --local-dir "$LOCAL_MODEL_DIR" \
    --local-dir-use-symlinks False
  echo "[startup] seeding GCS cache"
  gsutil -m rsync -r "$LOCAL_MODEL_DIR/" "gs://$BUCKET/$MODEL_ID/"
  echo "complete" | gsutil cp - "$SENTINEL"
fi

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
  --port 8000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.95

echo "[startup] waiting for vLLM to become ready..."
MAX_WAIT=300
WAITED=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  sleep 5
  WAITED=$((WAITED + 5))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[startup] ERROR: vLLM did not become ready after ${MAX_WAIT}s — last container logs:"
    docker logs vllm-server 2>&1 | tail -30
    exit 1
  fi
done
echo "[startup] vLLM ready at http://localhost:8000/v1"
