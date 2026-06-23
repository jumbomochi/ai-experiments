#!/bin/bash
# GCE startup script — rendered by Terraform templatefile().
# Runs once at instance boot; logs to GCE serial console.
set -euo pipefail

MODEL_ID="${model_id}"
BUCKET="${bucket_name}"
HF_TOKEN="${hf_token}"
VLLM_VERSION="${vllm_version}"
LOCAL_MODEL_DIR="/model"

echo "[startup] model_id=$MODEL_ID bucket=$BUCKET vllm=$VLLM_VERSION"

# Set HuggingFace token if provided (needed for gated models)
if [ -n "$HF_TOKEN" ]; then
  export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"
fi

mkdir -p "$LOCAL_MODEL_DIR"

# Check GCS cache — copy weights locally if present, else pull from HuggingFace
MODEL_GCS_PATH="gs://$BUCKET/$MODEL_ID"
if gsutil ls "$MODEL_GCS_PATH/" 2>/dev/null | grep -q .; then
  echo "[startup] cache hit — copying from $MODEL_GCS_PATH"
  gsutil -m cp -r "$MODEL_GCS_PATH/*" "$LOCAL_MODEL_DIR/"
else
  echo "[startup] cache miss — pulling from HuggingFace (this takes ~10 min for a 7B model)"
  pip install -q huggingface_hub
  python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('$MODEL_ID', local_dir='$LOCAL_MODEL_DIR')
"
  echo "[startup] seeding GCS cache at $MODEL_GCS_PATH"
  gsutil -m cp -r "$LOCAL_MODEL_DIR/" "$MODEL_GCS_PATH/"
fi

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

# Health-gate: poll until vLLM is ready (appears in serial console output)
echo "[startup] waiting for vLLM to become ready..."
until curl -sf http://localhost:8000/health; do
  sleep 5
done
echo "[startup] vLLM ready at http://localhost:8000/v1"
