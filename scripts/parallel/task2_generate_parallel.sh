#!/bin/bash
# Task 2 Data Generation Script - Parallel Domain Processing
# Usage: 
#   ./run_task2_data_generation_parallel.sh [model_name] [--api-key KEY] [--api-url URL] [--skip-render] [--stream]
#   This script will automatically split all domains and run them in parallel (one process per domain)
#
# Example:
#   ./run_task2_data_generation_parallel.sh gpt-5.2-codex --stream --api-key sk-xxx --api-url https://xxx/v1

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Parse arguments
MODEL="${1:-gpt-5.2-codex}"
shift || true

# Parse remaining arguments
SKIP_RENDER=""
API_KEY=""
API_URL=""
STREAM=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-render)
            SKIP_RENDER="--skip-render"
            shift
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --stream)
            STREAM="--stream"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [model_name] [--api-key KEY] [--api-url URL] [--skip-render] [--stream]"
            exit 1
            ;;
    esac
done

# Configuration
TARGET_DIR="${TARGET_DIR:-data/task2_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Get all domains
DOMAINS=($(ls -d "$TARGET_DIR"/domain_* 2>/dev/null | xargs -n1 basename | sort))

if [ ${#DOMAINS[@]} -eq 0 ]; then
    echo "ERROR: No domains found in $TARGET_DIR"
    exit 1
fi

echo "=========================================="
echo "Task 2 Data Generation - Parallel Processing"
echo "=========================================="
echo "Model: $MODEL"
echo "Total domains: ${#DOMAINS[@]}"
echo "Domains: ${DOMAINS[@]}"
if [ -n "$SKIP_RENDER" ]; then
    echo "Skip Render: Yes"
else
    echo "Skip Render: No"
fi
if [ -n "$STREAM" ]; then
    echo "Stream: Yes"
else
    echo "Stream: No"
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

# Build base command
BASE_CMD="./run_task2_data_generation.sh $MODEL"
if [ -n "$SKIP_RENDER" ]; then
    BASE_CMD="$BASE_CMD --skip-render"
fi
if [ -n "$STREAM" ]; then
    BASE_CMD="$BASE_CMD --stream"
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
echo "  ps aux | grep 'run_task2_data_generation.sh.*$MODEL'"
echo ""
echo "To check logs:"
echo "  tail -f $LOG_DIR/task2_data_generation_${MODEL//\//_}_*.log"
echo ""
echo "To stop all processes:"
echo "  pkill -f 'run_task2_data_generation.sh.*$MODEL'"
echo "=========================================="

