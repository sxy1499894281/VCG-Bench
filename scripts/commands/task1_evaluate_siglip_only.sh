#!/bin/bash
# Task 1 Evaluation Script - SigLIP Score Only
# Usage: 
#   Foreground: ./run_task1_evaluation_siglip_only.sh [model_name]
#   Background: nohup ./run_task1_evaluation_siglip_only.sh [model_name] > /dev/null 2>&1 &
# Example: ./run_task1_evaluation_siglip_only.sh gemini-3-pro-preview
#
# This script runs ONLY the siglip_score metric.
# Use this after running other metrics locally, to complete the evaluation on a server with GPU.

# nohup ./run_task1_evaluation_siglip_only.sh gemini-3-pro-preview > /dev/null 2>&1 &

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Default model (change this to switch models)
MODEL="${1:-gemini-3-pro-preview}"

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
LOG_FILE="$LOG_DIR/task1_evaluation_siglip_only_${MODEL_SANITIZED}_${TIMESTAMP}.log"

echo "=========================================="
echo "Task 1 Evaluation - SigLIP Score Only"
echo "Model: $MODEL"
echo "=========================================="
echo "Benchmark: $BENCHMARK_DIR"
echo "Output: $OUTPUT_DIR"
echo "Log: $LOG_FILE"
echo "=========================================="

# Build command - ONLY siglip_score metric
CMD="python eval/run_evaluation.py task1 \
    --benchmark \"$BENCHMARK_DIR\" \
    --output \"$OUTPUT_DIR\" \
    --models \"$MODEL\" \
    --metrics siglip_score"

# Uncomment the line below to pause before starting evaluation:
# read -p "Press Enter to start SigLIP score evaluation..."

# Run evaluation
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting SigLIP score evaluation..."
eval $CMD >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Evaluation failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] SigLIP score evaluation completed."

echo "=========================================="
echo "SigLIP Score Evaluation Completed!"
echo "Results: $OUTPUT_DIR"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Uncomment the line below to pause before script exits:
# read -p "Press Enter to exit..."

# Instructions for changing model:
# ==========================================
# This script runs ONLY the siglip_score metric (requires GPU).
# Use this after running ./run_task1_evaluation.sh to complete the evaluation.
#
# Workflow:
# 1. Run ./run_task1_evaluation.sh locally to evaluate all metrics except siglip_score
# 2. Run this script on a server with GPU to complete siglip_score
#    (incremental evaluation will automatically skip completed metrics)
#
# To change the model:
# 1. Pass model name as first argument:
#    ./run_task1_evaluation_siglip_only.sh your-model-name
#
# 2. Modify the MODEL variable on line 20:
#    MODEL="${1:-your-model-name}"
#
# 3. Set environment variable:
#    MODEL=your-model-name ./run_task1_evaluation_siglip_only.sh
#
# Common model names:
# - gemini-3-pro-preview
# - gpt-4o
# - claude-3-5-sonnet-20241022
#
# Available metrics for task1:
# - execution_success_rate (XESR)
# - xml_token_count (XTC)
# - style_consistency_score (SCS)
# - codevqa
# - siglip_score (this script only, requires GPU)
#
# ==========================================
# Background Execution and Process Management:
# ==========================================
# To run in background:
#   nohup ./run_task1_evaluation_siglip_only.sh [model_name] > /dev/null 2>&1 &
#
# To check if script is running:
#   ps aux | grep "run_task1_evaluation_siglip_only.sh"
#   ps aux | grep "python.*run_evaluation.py"
#
# To stop the background process:
#   1. Find the process ID (PID):
#      ps aux | grep "run_task1_evaluation_siglip_only.sh" | grep -v grep
#   2. Kill the process:
#      kill <PID>
#   Or kill all related processes:
#      pkill -f "run_task1_evaluation_siglip_only.sh"
#      pkill -f "python.*run_evaluation.py"
#
# To monitor the log file in real-time:
#   tail -f "$LOG_FILE"
#
# To check the last few lines of the log:
#   tail -n 50 "$LOG_FILE"
# ==========================================

