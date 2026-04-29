#!/bin/bash
# Start vLLM inference server for code4u.ai
# 
# Prerequisites:
#   - NVIDIA GPU (L40S or A100 recommended)
#   - CUDA 12.1+
#   - pip install vllm>=0.3.0
#
# Usage:
#   ./scripts/start_inference.sh [--model MODEL] [--lora PATH]

set -e

# Default configuration
MODEL="${MODEL:-Qwen/Qwen2.5-Coder-32B}"
LORA_PATH="${LORA_PATH:-./lora-adapters/code4u}"
PORT="${PORT:-8001}"
GPU_UTIL="${GPU_UTIL:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
TENSOR_PARALLEL="${TENSOR_PARALLEL:-2}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --lora)
            LORA_PATH="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --single-gpu)
            TENSOR_PARALLEL=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              code4u.ai vLLM Inference Server                 ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Model:          ${MODEL}"
echo "║  LoRA Adapter:   ${LORA_PATH}"
echo "║  Port:           ${PORT}"
echo "║  GPU Util:       ${GPU_UTIL}"
echo "║  Tensor Parallel: ${TENSOR_PARALLEL}"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if LoRA adapter exists
if [ -d "$LORA_PATH" ]; then
    LORA_ARGS="--enable-lora --lora-modules code4u=${LORA_PATH}"
    echo "✓ LoRA adapter found"
else
    LORA_ARGS=""
    echo "⚠ No LoRA adapter found at ${LORA_PATH}, running base model"
fi

# Start vLLM server
echo ""
echo "Starting vLLM server..."
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    $LORA_ARGS \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_UTIL" \
    --tensor-parallel-size "$TENSOR_PARALLEL" \
    --trust-remote-code \
    --host 0.0.0.0 \
    --port "$PORT"

