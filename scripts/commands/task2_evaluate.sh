#!/bin/bash
# Task 2 Evaluation Script (Single Model)
# Usage: 
#   Foreground: ./run_task2_evaluation.sh [model_name] [--disable-metrics METRIC1 METRIC2 ...] [--api-key KEY] [--api-url URL]
#   Background: nohup ./run_task2_evaluation.sh [model_name] [--disable-metrics ...] [--api-key KEY] [--api-url URL] > /dev/null 2>&1 &
# Example: ./run_task2_evaluation.sh gemini-3-pro-preview --disable-metrics hdrfr
# Example: ./run_task2_evaluation.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com

#nohup ./run_task2_evaluation.sh gemini-3-pro-preview > /dev/null 2>&1 &

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Default model (change this to switch models)
MODEL="${1:-gemini-3-pro-preview}"

# Shift to get remaining arguments
shift 2>/dev/null || true

# Parse arguments for --disable-metrics, --api-key, --api-url, and --domain
DISABLE_METRICS_ARGS=""
API_KEY=""
API_URL=""
DOMAIN_ARGS=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --disable-metrics)
            shift
            # Collect metric names until next option or end of arguments
            DISABLE_METRICS_ARGS="--disable-metrics"
            while [[ $# -gt 0 ]]; do
                # Check if current argument starts with --
                if [[ "$1" == --* ]]; then
                    break
                fi
                DISABLE_METRICS_ARGS="$DISABLE_METRICS_ARGS $1"
                shift
            done
            ;;
        --api-key)
            shift
            if [[ $# -gt 0 && "$1" != --* ]]; then
                API_KEY="$1"
                shift
            else
                echo "ERROR: --api-key requires a value"
                exit 1
            fi
            ;;
        --api-url)
            shift
            if [[ $# -gt 0 && "$1" != --* ]]; then
                API_URL="$1"
                shift
            else
                echo "ERROR: --api-url requires a value"
                exit 1
            fi
            ;;
        --domain)
            shift
            # Collect domain names until next option or end of arguments
            DOMAIN_ARGS="--domain"
            while [[ $# -gt 0 ]]; do
                # Check if current argument starts with --
                if [[ "$1" == --* ]]; then
                    break
                fi
                DOMAIN_ARGS="$DOMAIN_ARGS $1"
                shift
            done
            ;;
        *)
            # Unknown argument, might be part of --disable-metrics or --domain
            shift
            ;;
    esac
done

# Configuration (modify these paths as needed)
BENCHMARK_DIR="${BENCHMARK_DIR:-data/task2_benchmark}"
OUTPUT_DIR="${OUTPUT_DIR:-data/task2_evaluation}"
LOG_DIR="${LOG_DIR:-logs}"

# Create directories if they don't exist
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOG_DIR"

# Log file with timestamp
# Sanitize model name for filename (replace / with _)
MODEL_SANITIZED=$(echo "$MODEL" | sed 's/\//_/g')
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task2_evaluation_${MODEL_SANITIZED}_${TIMESTAMP}.log"

echo "=========================================="
echo "Task 2 Evaluation - Model: $MODEL"
echo "=========================================="
echo "Benchmark: $BENCHMARK_DIR"
echo "Output: $OUTPUT_DIR"
echo "Log: $LOG_FILE"
if [ -n "$DISABLE_METRICS_ARGS" ]; then
    echo "Disabled metrics: $DISABLE_METRICS_ARGS"
fi
if [ -n "$API_KEY" ]; then
    echo "API Key: [SET]"
else
    echo "API Key: [Using .env file]"
fi
if [ -n "$API_URL" ]; then
    echo "API URL: $API_URL"
else
    echo "API URL: [Using .env file]"
fi
echo "=========================================="

# Build command
BASE_CMD="python eval/run_evaluation.py task2 \
    --benchmark \"$BENCHMARK_DIR\" \
    --output \"$OUTPUT_DIR\" \
    --models \"$MODEL\""

CMD="$BASE_CMD"

# Add disabled metrics if provided
if [ -n "$DISABLE_METRICS_ARGS" ]; then
    CMD="$CMD $DISABLE_METRICS_ARGS"
fi

# Add domain filter if provided
if [ -n "$DOMAIN_ARGS" ]; then
    CMD="$CMD $DOMAIN_ARGS"
fi

# Uncomment the line below to pause before starting evaluation:
# read -p "Press Enter to start evaluation..."

# Set environment variables if provided
ENV_VARS=""
if [ -n "$API_KEY" ]; then
    export CUSTOM_API_KEY="$API_KEY"
    ENV_VARS="CUSTOM_API_KEY=\"$API_KEY\" "
fi
if [ -n "$API_URL" ]; then
    export CUSTOM_BASE_URL="$API_URL"
    ENV_VARS="${ENV_VARS}CUSTOM_BASE_URL=\"$API_URL\" "
fi

# Run evaluation
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting evaluation..."
if [ -n "$ENV_VARS" ]; then
    eval $ENV_VARS $CMD >> "$LOG_FILE" 2>&1
else
    eval $CMD >> "$LOG_FILE" 2>&1
fi

if [ $? -ne 0 ]; then
    echo "ERROR: Evaluation failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Evaluation completed."

echo "=========================================="
echo "Task 2 Evaluation Completed!"
echo "Results: $OUTPUT_DIR"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Uncomment the line below to pause before script exits:
# read -p "Press Enter to exit..."

# Instructions for changing model and disabling metrics:
# ==========================================
# To change the model:
# 1. Pass model name as first argument:
#    ./run_task2_evaluation.sh your-model-name
#
# 2. Modify the MODEL variable on line 11:
#    MODEL="${1:-your-model-name}"
#
# To disable metrics:
# 1. Pass --disable-metrics as arguments:
#    ./run_task2_evaluation.sh gemini-3-pro-preview --disable-metrics hdrfr
#
# 2. Modify line 15 to add default disabled metrics:
#    DISABLE_METRICS_ARGS="${@:2} --disable-metrics hdrfr"
#
# To specify API key and URL (for gemini, gpt, claude):
# 1. Pass --api-key and --api-url as arguments:
#    ./run_task2_evaluation.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com
#    (If not specified, will use values from .env file)
#
# Available metrics for task2:
# - modified_xml_execution_success_rate (MXESR)
# - modification_json_token_count (MJTC)
# - hdrfr
# - xml_edit_distance (XED)
#
# Example: Disable hdrfr (time-consuming):
#    ./run_task2_evaluation.sh gemini-3-pro-preview --disable-metrics hdrfr
#
# To re-run only disabled metrics later:
#    Remove --disable-metrics flag and run again (incremental evaluation will skip completed metrics)
#
# ==========================================
# Background Execution and Process Management:
# ==========================================
# To run in background:
#   nohup ./run_task2_evaluation.sh [model_name] [--disable-metrics ...] > /dev/null 2>&1 &
#
# To check if script is running:
#   ps aux | grep "run_task2_evaluation.sh"
#   ps aux | grep "python.*run_evaluation.py"
#
# To stop the background process:
#   1. Find the process ID (PID):
#      ps aux | grep "run_task2_evaluation.sh" | grep -v grep
#   2. Kill the process:
#      kill <PID>
#   Or kill all related processes:
#      pkill -f "run_task2_evaluation.sh"
#      pkill -f "python.*run_evaluation.py"
#
# To monitor the log file in real-time:
#   tail -f "$LOG_FILE"
#
# To check the last few lines of the log:
#   tail -n 50 "$LOG_FILE"
# ==========================================

