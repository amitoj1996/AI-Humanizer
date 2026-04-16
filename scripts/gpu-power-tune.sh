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
#   sudo ./scripts/gpu-power-tune.sh                    # apply default 160W to all
#   sudo ./scripts/gpu-power-tune.sh 150                # shortcut: apply 150W
#   sudo ./scripts/gpu-power-tune.sh 160 0              # apply 160W to GPU 0 only
#   sudo ./scripts/gpu-power-tune.sh apply 160          # explicit form
#   sudo ./scripts/gpu-power-tune.sh apply 160 0        # explicit form, one GPU
#   sudo ./scripts/gpu-power-tune.sh reset              # restore stock power limit
#   ./scripts/gpu-power-tune.sh status                  # show current limits
#
# Unknown subcommands exit non-zero — this script mutates hardware state,
# so a typo must fail loud, not silently power-cap every GPU.
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
    # Query only the two fields we need with a comma field-separator, so
    # GPU names with spaces (e.g. "NVIDIA GeForce RTX 3070") don't break
    # the parse.  `IFS=,` + `read -r` gives us clean CSV columns.
    while IFS=, read -r idx default; do
      idx=$(echo "$idx" | tr -d ' ')
      default=$(echo "$default" | tr -d ' ')
      [[ -z "$idx" || -z "$default" ]] && continue
      echo "resetting GPU $idx to ${default}W"
      nvidia-smi -i "$idx" -pl "$default"
    done < <(nvidia-smi --query-gpu=index,power.default_limit \
                        --format=csv,noheader,nounits)
    ;;
  apply)
    limit="${2:-$DEFAULT_LIMIT}"
    if ! [[ "$limit" =~ ^[0-9]+$ ]]; then limit="$DEFAULT_LIMIT"; fi
    target_gpu="${3:-all}"
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
  *)
    # Back-compat shortcut: a bare number is treated as an apply limit
    # (`sudo ./gpu-power-tune.sh 150` was the documented form). Anything
    # else is a typo — refuse to touch hardware on ambiguous input.
    if [[ "$cmd" =~ ^[0-9]+$ ]]; then
      exec "$0" apply "$cmd" "${2:-all}"
    fi
    echo "error: unknown subcommand '$cmd'" >&2
    echo "usage: $0 [apply [<watts> [<gpu_idx>|all]] | reset | status]" >&2
    exit 2
    ;;
esac
