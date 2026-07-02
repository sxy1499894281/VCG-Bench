#!/bin/bash
# Task 1 Evaluation Script - Parallel Domain Processing
# Usage: 
#   ./run_task1_evaluation_parallel.sh [model_name] [--disable-metrics METRIC1 METRIC2 ...] [--api-key KEY] [--api-url URL]
#   This script will automatically split all domains and run them in parallel (one process per domain)
#
# Example:
#   ./run_task1_evaluation_parallel.sh gemini-3-pro-preview --disable-metrics siglip_score

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
MODEL="${1:-gemini-3-pro-preview}"
shift || true

# Parse remaining arguments
DISABLE_METRICS_ARGS=""
API_KEY=""
API_URL=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --disable-metrics)
            shift
            DISABLE_METRICS_ARGS="--disable-metrics"
            while [[ $# -gt 0 ]]; do
                if [[ "$1" == --* ]]; then
                    break
                fi
                DISABLE_METRICS_ARGS="$DISABLE_METRICS_ARGS $1"
                shift
            done
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [model_name] [--disable-metrics METRIC1 METRIC2 ...] [--api-key KEY] [--api-url URL]"
            exit 1
            ;;
    esac
done

# Configuration
BENCHMARK_DIR="${BENCHMARK_DIR:-data/task1_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Get all domains
DOMAINS=($(ls -d "$BENCHMARK_DIR"/domain_* 2>/dev/null | xargs -n1 basename | sort))

if [ ${#DOMAINS[@]} -eq 0 ]; then
    echo "ERROR: No domains found in $BENCHMARK_DIR"
    exit 1
fi

echo "=========================================="
echo "Task 1 Evaluation - Parallel Processing"
echo "=========================================="
echo "Model: $MODEL"
echo "Total domains: ${#DOMAINS[@]}"
echo "Domains: ${DOMAINS[@]}"
if [ -n "$DISABLE_METRICS_ARGS" ]; then
    echo "Disabled metrics: $DISABLE_METRICS_ARGS"
fi
if [ -n "$API_KEY" ]; then
    echo "API Key: ${API_KEY:0:10}... (set)"
else
    echo "API Key: (using environment variable CUSTOM_API_KEY)"
fi
if [ -n "$API_URL" ]; then
    echo "API URL: $API_URL"
else
    echo "API URL: (using environment variable CUSTOM_BASE_URL)"
fi
echo "=========================================="
echo ""
echo "Note: All domains will write to the same detailed_results.json file."
echo "      The evaluation code uses retry mechanism to handle concurrent writes."
echo ""

# Build base command
BASE_CMD="./run_task1_evaluation.sh $MODEL"
if [ -n "$DISABLE_METRICS_ARGS" ]; then
    BASE_CMD="$BASE_CMD $DISABLE_METRICS_ARGS"
fi
if [ -n "$API_KEY" ]; then
    BASE_CMD="$BASE_CMD --api-key $API_KEY"
fi
if [ -n "$API_URL" ]; then
    BASE_CMD="$BASE_CMD --api-url $API_URL"
fi

# Launch parallel jobs (one process per domain)
PIDS=()
for domain in "${DOMAINS[@]}"; do
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting domain: $domain"
    CMD="$BASE_CMD --domain $domain"
    nohup $CMD > /dev/null 2>&1 &
    PID=$!
    PIDS+=($PID)
    echo "  Started with PID: $PID"
    # Small delay to avoid overwhelming the system
    sleep 1
done

echo ""
echo "=========================================="
echo "All domains started in parallel"
echo "=========================================="
echo "Total processes: ${#PIDS[@]}"
echo "PIDs: ${PIDS[@]}"
echo ""
echo "To monitor progress:"
echo "  ps aux | grep 'run_task1_evaluation.sh.*$MODEL'"
echo ""
echo "To check logs:"
echo "  tail -f $LOG_DIR/task1_evaluation_${MODEL//\//_}_*.log"
echo ""
echo "To stop all processes:"
echo "  pkill -f 'run_task1_evaluation.sh.*$MODEL'"
echo "=========================================="

