#!/bin/bash
# Task 1 End-to-End Orchestrator
# Default workflow: Gemini API evaluation flow
#
# Usage:
#   ./task1.sh
#   ./task1.sh gpt-5.1 --domain domain_ai domain_biology
#   ./task1.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com
#   ./task1.sh gemini-3-pro-preview --disable-metrics siglip_score
#   ./task1.sh gemini-3-pro-preview --force-prepare-gt
#   ./task1.sh gemini-3-pro-preview --skip-render
#   ./task1.sh gemini-3-pro-preview --skip-eval
#   ./task1.sh gemini-3-pro-preview --source data/raw_picture --target data/task1_benchmark

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODEL="${1:-gemini-3-pro-preview}"
shift || true

SOURCE_DIR="${SOURCE_DIR:-data/raw_picture}"
TARGET_DIR="${TARGET_DIR:-data/task1_benchmark}"

DOMAIN_VALUES=()
DOMAIN_ARGS=()
GEN_ARGS=()
EVAL_ARGS=()
FORCE_PREPARE_GT=0
SKIP_EVAL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            if [[ $# -lt 2 || "$2" == --* ]]; then
                echo "ERROR: --source requires a value."
                exit 1
            fi
            SOURCE_DIR="$2"
            shift 2
            ;;
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
            echo "Run ./task1.sh [model] [--source DIR] [--target DIR] [--domain ...] [--skip-render] [--skip-eval] [--api-key KEY] [--api-url URL] [--disable-metrics ...] [--force-prepare-gt]"
            exit 1
            ;;
    esac
done

# Forward domain filters to generation/evaluation steps
if [[ ${#DOMAIN_ARGS[@]} -gt 0 ]]; then
    GEN_ARGS+=("${DOMAIN_ARGS[@]}")
    EVAL_ARGS+=("${DOMAIN_ARGS[@]}")
fi

# Export so sub-scripts pick them up
export SOURCE_DIR
export TARGET_DIR

echo "=========================================="
echo "Task 1 Full Workflow"
echo "=========================================="
echo "Model: $MODEL"
if [[ ${#DOMAIN_VALUES[@]} -gt 0 ]]; then
    echo "Domains: ${DOMAIN_VALUES[*]}"
else
    echo "Domains: All"
fi
echo "Source dir: $SOURCE_DIR"
echo "Target dir: $TARGET_DIR"
echo "=========================================="

echo ""
echo "[1/3] Data generation"
bash "scripts/commands/task1_generate.sh" "$MODEL" "${GEN_ARGS[@]}"

echo ""
echo "[2/3] Prepare ground truth"
if [[ $SKIP_EVAL -eq 1 ]]; then
    echo "Skipping ground truth preparation (--skip-eval)."
else
    SAMPLE_COUNT=0
    QA_COUNT=0

    if [[ ${#DOMAIN_VALUES[@]} -gt 0 ]]; then
        for domain in "${DOMAIN_VALUES[@]}"; do
            domain_dir="$TARGET_DIR/$domain"
            if [[ -d "$domain_dir" ]]; then
                for sample_dir in "$domain_dir"/sample_*; do
                    if [[ -d "$sample_dir" ]]; then
                        SAMPLE_COUNT=$((SAMPLE_COUNT + 1))
                        if [[ -f "$sample_dir/qa_pairs.json" ]]; then
                            QA_COUNT=$((QA_COUNT + 1))
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
                        if [[ -f "$sample_dir/qa_pairs.json" ]]; then
                            QA_COUNT=$((QA_COUNT + 1))
                        fi
                    fi
                done
            fi
        done
    fi

    if [[ $FORCE_PREPARE_GT -eq 1 ]]; then
        echo "Force mode enabled: preparing ground truth."
        bash "scripts/commands/task1_prepare_gt.sh" "${DOMAIN_ARGS[@]}"
    elif [[ $QA_COUNT -gt 0 ]]; then
        echo "Detected existing QA pairs ($QA_COUNT/$SAMPLE_COUNT samples). Skipping ground truth preparation."
    else
        echo "No existing QA pairs found. Preparing ground truth with Gemini..."
        bash "scripts/commands/task1_prepare_gt.sh" "${DOMAIN_ARGS[@]}"
    fi
fi

echo ""
echo "[3/3] Evaluation"
if [[ $SKIP_EVAL -eq 1 ]]; then
    echo "Skipping evaluation (--skip-eval)."
else
    bash "scripts/commands/task1_evaluate.sh" "$MODEL" "${EVAL_ARGS[@]}"
fi

echo ""
echo "=========================================="
echo "Task 1 workflow completed."
echo "=========================================="
