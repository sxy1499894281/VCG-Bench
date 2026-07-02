#!/bin/bash
# Task 2 End-to-End Orchestrator
# Default workflow: Gemini API evaluation flow
#
# Usage:
#   ./task2.sh
#   ./task2.sh gpt-5.1 --domain domain_ai domain_biology
#   ./task2.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com
#   ./task2.sh gemini-3-pro-preview --disable-metrics hdrfr
#   ./task2.sh gemini-3-pro-preview --force-prepare-gt
#   ./task2.sh gemini-3-pro-preview --skip-render
#   ./task2.sh gemini-3-pro-preview --skip-eval
#   ./task2.sh gemini-3-pro-preview --stream
#   ./task2.sh gemini-3-pro-preview --target data/demo_task2_benchmark

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${1:-gemini-3-pro-preview}"
shift || true

TARGET_DIR="${TARGET_DIR:-data/task2_benchmark}"

DOMAIN_VALUES=()
DOMAIN_ARGS=()
GEN_ARGS=()
EVAL_ARGS=()
FORCE_PREPARE_GT=0
SKIP_EVAL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "ERROR: --target requires a value."
                exit 1
            fi
            TARGET_DIR="$2"
            shift 2
            ;;
        --domain)
            shift
            if [[ $# -eq 0 || "$1" == --* ]]; then
                echo "ERROR: --domain requires at least one domain value."
                exit 1
            fi
            while [[ $# -gt 0 && "$1" != --* ]]; do
                DOMAIN_VALUES+=("$1")
                DOMAIN_ARGS+=("--domain" "$1")
                shift
            done
            ;;
        --skip-render)
            GEN_ARGS+=("--skip-render")
            shift
            ;;
        --stream)
            GEN_ARGS+=("--stream")
            shift
            ;;
        --api-key)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "ERROR: --api-key requires a value."
                exit 1
            fi
            GEN_ARGS+=("--api-key" "$2")
            EVAL_ARGS+=("--api-key" "$2")
            shift 2
            ;;
        --api-url)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "ERROR: --api-url requires a value."
                exit 1
            fi
            GEN_ARGS+=("--api-url" "$2")
            EVAL_ARGS+=("--api-url" "$2")
            shift 2
            ;;
        --disable-metrics)
            EVAL_ARGS+=("--disable-metrics")
            shift
            if [[ $# -eq 0 || "$1" == --* ]]; then
                echo "ERROR: --disable-metrics requires at least one metric."
                exit 1
            fi
            while [[ $# -gt 0 && "$1" != --* ]]; do
                EVAL_ARGS+=("$1")
                shift
            done
            ;;
        --force-prepare-gt)
            FORCE_PREPARE_GT=1
            shift
            ;;
        --skip-eval)
            SKIP_EVAL=1
            shift
            ;;
        *)
            echo "ERROR: Unknown argument: $1"
            echo "Run ./task2.sh [model] [--target DIR] [--domain ...] [--skip-render] [--skip-eval] [--stream] [--api-key KEY] [--api-url URL] [--disable-metrics ...] [--force-prepare-gt]"
            exit 1
            ;;
    esac
done

# Forward domain filters to generation/evaluation steps
if [[ ${#DOMAIN_ARGS[@]} -gt 0 ]]; then
    GEN_ARGS+=("${DOMAIN_ARGS[@]}")
    EVAL_ARGS+=("${DOMAIN_ARGS[@]}")
fi

# Export so sub-scripts pick it up
export TARGET_DIR

echo "=========================================="
echo "Task 2 Full Workflow"
echo "=========================================="
echo "Model: $MODEL"
if [[ ${#DOMAIN_VALUES[@]} -gt 0 ]]; then
    echo "Domains: ${DOMAIN_VALUES[*]}"
else
    echo "Domains: All"
fi
echo "Target dir: $TARGET_DIR"
echo "=========================================="

echo ""
echo "[1/4] Prepare ground truth"
SAMPLE_COUNT=0
GT_COUNT=0

if [[ ${#DOMAIN_VALUES[@]} -gt 0 ]]; then
    for domain in "${DOMAIN_VALUES[@]}"; do
        domain_dir="$TARGET_DIR/$domain"
        if [[ -d "$domain_dir" ]]; then
            for sample_dir in "$domain_dir"/sample_*; do
                if [[ -d "$sample_dir" ]]; then
                    SAMPLE_COUNT=$((SAMPLE_COUNT + 1))
                    shopt -s nullglob
                    qs_files=("$sample_dir"/instructions/inst_*/question_set.json)
                    shopt -u nullglob
                    if [[ ${#qs_files[@]} -gt 0 ]]; then
                        GT_COUNT=$((GT_COUNT + 1))
                    fi
                fi
            done
        fi
    done
else
    for domain_dir in "$TARGET_DIR"/domain_*; do
        if [[ -d "$domain_dir" ]]; then
            for sample_dir in "$domain_dir"/sample_*; do
                if [[ -d "$sample_dir" ]]; then
                    SAMPLE_COUNT=$((SAMPLE_COUNT + 1))
                    shopt -s nullglob
                    qs_files=("$sample_dir"/instructions/inst_*/question_set.json)
                    shopt -u nullglob
                    if [[ ${#qs_files[@]} -gt 0 ]]; then
                        GT_COUNT=$((GT_COUNT + 1))
                    fi
                fi
            done
        fi
    done
fi

if [[ $FORCE_PREPARE_GT -eq 1 ]]; then
    echo "Force mode enabled: preparing ground truth."
    bash "scripts/commands/task2_prepare_gt.sh" "${DOMAIN_ARGS[@]}"
elif [[ $GT_COUNT -gt 0 ]]; then
    echo "Detected existing ground truth ($GT_COUNT/$SAMPLE_COUNT samples). Skipping ground truth preparation."
else
    echo "No existing ground truth found. Preparing ground truth with Gemini..."
    bash "scripts/commands/task2_prepare_gt.sh" "${DOMAIN_ARGS[@]}"
fi

echo ""
echo "[2/4] Data generation"
bash "scripts/commands/task2_generate.sh" "$MODEL" "${GEN_ARGS[@]}"

echo ""
echo "[3/4] Evaluation"
if [[ $SKIP_EVAL -eq 1 ]]; then
    echo "Skipping evaluation (--skip-eval)."
else
    bash "scripts/commands/task2_evaluate.sh" "$MODEL" "${EVAL_ARGS[@]}"
fi

echo ""
echo "[4/4] Export dataset JSON"
if [[ $SKIP_EVAL -eq 1 ]]; then
    echo "Skipping dataset export (--skip-eval)."
else
    python scripts/task2/export_dataset_json.py \
        --source "$TARGET_DIR" \
        --output "$TARGET_DIR/dataset.json"
fi

echo ""
echo "=========================================="
echo "Task 2 workflow completed."
echo "=========================================="
