#!/bin/bash
# Task 1 Evaluation Script (Single Model)
# Usage: 
#   Foreground: ./run_task1_evaluation.sh [model_name] [--disable-metrics METRIC1 METRIC2 ...] [--api-key KEY] [--api-url URL]
#   Background: nohup ./run_task1_evaluation.sh [model_name] [--disable-metrics ...] [--api-key KEY] [--api-url URL] > /dev/null 2>&1 &
# Example: ./run_task1_evaluation.sh gemini-3-pro-preview --disable-metrics siglip_score
# Example: ./run_task1_evaluation.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com

# nohup ./run_task1_evaluation.sh gemini-3-pro-preview --disable-metrics siglip_score > /dev/null 2>&1 &

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
BENCHMARK_DIR="${BENCHMARK_DIR:-data/task1_benchmark}"
OUTPUT_DIR="${OUTPUT_DIR:-data/task1_evaluation}"
LOG_DIR="${LOG_DIR:-logs}"

# Create directories if they don't exist
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOG_DIR"

# Log file with timestamp
# Sanitize model name for filename (replace / with _)
MODEL_SANITIZED=$(echo "$MODEL" | sed 's/\//_/g')
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
# Add domain to log filename if specified, and add process ID to avoid conflicts
if [ -n "$DOMAIN_ARGS" ]; then
    # Extract domain name from DOMAIN_ARGS (format: --domain domain_name)
    DOMAIN_NAME=$(echo "$DOMAIN_ARGS" | awk '{print $2}' | sed 's/domain_//g')
    LOG_FILE="$LOG_DIR/task1_evaluation_${MODEL_SANITIZED}_${DOMAIN_NAME}_${TIMESTAMP}_$$.log"
else
    LOG_FILE="$LOG_DIR/task1_evaluation_${MODEL_SANITIZED}_${TIMESTAMP}_$$.log"
fi

echo "=========================================="
echo "Task 1 Evaluation - Model: $MODEL"
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

# Build command - Run all metrics by default (use --disable-metrics to disable specific metrics)
BASE_CMD="python eval/run_evaluation.py task1 \
    --benchmark \"$BENCHMARK_DIR\" \
    --output \"$OUTPUT_DIR\" \
    --models \"$MODEL\""

# Add disabled metrics only if specified by user
if [ -n "$DISABLE_METRICS_ARGS" ]; then
    CMD="$BASE_CMD $DISABLE_METRICS_ARGS"
else
    CMD="$BASE_CMD"
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
# Write startup info to log file (even when using nohup with > /dev/null)
echo "==========================================" > "$LOG_FILE"
echo "Task 1 Evaluation - Model: $MODEL" >> "$LOG_FILE"
echo "Started at: $(date +'%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "Log file: $LOG_FILE" >> "$LOG_FILE"
if [ -n "$DOMAIN_ARGS" ]; then
    echo "Domain: $DOMAIN_ARGS" >> "$LOG_FILE"
fi
echo "Command: $CMD" >> "$LOG_FILE"
echo "==========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting evaluation..."
echo "[INFO] Log file: $LOG_FILE"  # This will be visible even with > /dev/null if run in foreground
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
echo "Task 1 Evaluation Completed!"
echo "Results: $OUTPUT_DIR"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Uncomment the line below to pause before script exits:
# read -p "Press Enter to exit..."

# Instructions for changing model and disabling metrics:
# ==========================================
# This script runs ALL metrics by default. Use --disable-metrics to disable specific metrics.
# 
# To disable siglip_score (if GPU is not available):
#    ./run_task1_evaluation.sh gemini-3-pro-preview --disable-metrics siglip_score
#
# To run only siglip_score separately (on a server with GPU):
#    ./run_task1_evaluation_siglip_only.sh gemini-3-pro-preview
#    (incremental evaluation will automatically skip completed metrics)
#
# To change the model:
# 1. Pass model name as first argument:
#    ./run_task1_evaluation.sh your-model-name
#
# 2. Modify the MODEL variable on line 17:
#    MODEL="${1:-your-model-name}"
#
# 3. Set environment variable:
#    MODEL=your-model-name ./run_task1_evaluation.sh
#
# To disable specific metrics:
# 1. Pass --disable-metrics as arguments:
#    ./run_task1_evaluation.sh gemini-3-pro-preview --disable-metrics siglip_score codevqa
#    (This will disable both siglip_score and codevqa)
#
# To specify API key and URL (for gemini, gpt, claude):
# 1. Pass --api-key and --api-url as arguments:
#    ./run_task1_evaluation.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com
#    (If not specified, will use values from .env file)
#
# Available metrics for task1:
# - execution_success_rate (XESR)
# - xml_token_count (XTC)
# - style_consistency_score (SCS)
# - codevqa
# - siglip_score (requires GPU, can be disabled with --disable-metrics siglip_score)
#
# ==========================================
# Background Execution and Process Management:
# ==========================================
# To run in background:
#   nohup ./run_task1_evaluation.sh [model_name] [--disable-metrics ...] > /dev/null 2>&1 &
#
# To check if script is running:
#   ps aux | grep "run_task1_evaluation.sh"
#   ps aux | grep "python.*run_evaluation.py"
#
# To stop the background process:
#   1. Find the process ID (PID):
#      ps aux | grep "run_task1_evaluation.sh" | grep -v grep
#   2. Kill the process:
#      kill <PID>
#   Or kill all related processes:
#      pkill -f "run_task1_evaluation.sh"
#      pkill -f "python.*run_evaluation.py"
#
# To monitor the log file in real-time:
#   tail -f "$LOG_FILE"
#
# To check the last few lines of the log:
#   tail -n 50 "$LOG_FILE"
# ==========================================

