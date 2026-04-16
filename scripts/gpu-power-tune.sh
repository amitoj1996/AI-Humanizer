#!/usr/bin/env bash
# GPU power-limit helper for AI-Humanizer on NVIDIA Ampere+ cards.
#
# Why: Inference workloads (what this app does) are usually memory-bandwidth
# bound, not compute bound. That means you can reduce the GPU power limit
# substantially — research consistently shows Ampere cards keep ~93-97% of
# inference throughput at 70-75% of stock TDP while dropping power draw by
# 25-30%, running much cooler and quieter.
#
# For a 2x RTX 3070 (220W stock TDP each, 440W total):
#   - Default: 220W each
#   - Recommended for this app: 160W each (~73% TDP, ~95% perf)
#   - Aggressive: 140W each (~64% TDP, ~88% perf — noticeably slower)
#
# Usage:
#   sudo ./scripts/gpu-power-tune.sh              # apply default 160W to all GPUs
#   sudo ./scripts/gpu-power-tune.sh 150          # apply 150W to all GPUs
#   sudo ./scripts/gpu-power-tune.sh 160 0        # apply 160W to GPU 0 only
#   sudo ./scripts/gpu-power-tune.sh reset        # restore stock power limit
#   ./scripts/gpu-power-tune.sh status            # show current limits (no sudo)
#
# To persist across reboots, add a systemd unit — see Puget Systems guide
# linked in repo docs.
#
# Source research:
#   - Puget Systems: "Quad RTX3090 GPU Power Limiting" — 280W (vs 350W stock)
#     gave 95% perf. Same tradeoff shape applies to 3070.
#   - Tim Harbakon's NVIDIA GPU Power Optimization guide.
set -euo pipefail

DEFAULT_LIMIT=160  # watts per 3070; edit for a different card

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "error: nvidia-smi not found. Install NVIDIA drivers first." >&2
  exit 1
fi

cmd="${1:-apply}"

show_status() {
  nvidia-smi --query-gpu=index,name,power.limit,power.default_limit,power.min_limit,power.max_limit,power.draw \
             --format=csv,noheader,nounits
}

case "$cmd" in
  status)
    echo "idx, name, current_limit_W, stock_limit_W, min_W, max_W, current_draw_W"
    show_status
    ;;
  reset)
    if [[ $EUID -ne 0 ]]; then echo "error: reset needs sudo" >&2; exit 1; fi
    # --power-limit without a value resets to default on most driver versions;
    # portable approach is to query default and re-apply it.
    while read -r idx _ _ default _ _ _; do
      idx=${idx%,}; default=${default%,}
      echo "resetting GPU $idx to ${default}W"
      nvidia-smi -i "$idx" -pl "$default"
    done < <(show_status)
    ;;
  apply|*)
    limit="${1:-$DEFAULT_LIMIT}"
    # If first arg wasn't numeric (e.g. 'apply'), fall back to default.
    if ! [[ "$limit" =~ ^[0-9]+$ ]]; then limit="$DEFAULT_LIMIT"; fi
    target_gpu="${2:-all}"
    if [[ $EUID -ne 0 ]]; then echo "error: apply needs sudo" >&2; exit 1; fi

    echo "applying ${limit}W power limit to GPU ${target_gpu}"
    if [[ "$target_gpu" == "all" ]]; then
      nvidia-smi -pl "$limit"
    else
      nvidia-smi -i "$target_gpu" -pl "$limit"
    fi
    echo "--- new state ---"
    show_status
    ;;
esac
