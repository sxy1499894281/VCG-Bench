#!/bin/bash
# Task 2 Data Generation Script (Single Model)
# Usage: 
#   Foreground: ./run_task2_data_generation.sh [model_name] [--domain domain1 domain2 ...] [--skip-render] [--api-key KEY] [--api-url URL] [--stream]
#   Background: nohup ./run_task2_data_generation.sh [model_name] [--api-key KEY] [--api-url URL] [--stream] > /dev/null 2>&1 &
# Example: ./run_task2_data_generation.sh gemini-3-pro-preview
# Example: ./run_task2_data_generation.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com
# Example: ./run_task2_data_generation.sh gpt-5.2-codex --stream  # Use streaming for codex model

#nohup ./run_task2_data_generation.sh gemini-3-pro-preview > /dev/null 2>&1 &

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
# Usage: ./run_task2_data_generation.sh [model_name] [--domain domain1 domain2 ...] [--skip-render] [--api-key KEY] [--api-url URL]
MODEL="${1:-gemini-3-pro-preview}"
shift || true  # Remove first argument (model name)

# Parse remaining arguments for --domain, --skip-render, --api-key, --api-url, and --stream
DOMAIN_ARGS=()
SKIP_RENDER=""
API_KEY=""
API_URL=""
STREAM=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            shift
            # Collect domain names until next option or end of arguments
            while [[ $# -gt 0 ]]; do
                # Check if current argument starts with --
                if [[ "$1" == --* ]]; then
                    break
                fi
                DOMAIN_ARGS+=("--domain" "$1")
                shift
            done
            ;;
        --skip-render)
            SKIP_RENDER="--skip-render"
            shift
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
        --stream)
            STREAM="--stream"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Configuration (modify these paths as needed)
# Note: Task 2 uses task2_benchmark as both source and target
# The task2_benchmark should already contain extracted Gemini data from Task 1
TARGET_DIR="${TARGET_DIR:-data/task2_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file with timestamp
# Sanitize model name for filename (replace / with _)
MODEL_SANITIZED=$(echo "$MODEL" | sed 's/\//_/g')
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task2_data_generation_${MODEL_SANITIZED}_${TIMESTAMP}.log"

echo "=========================================="
echo "Task 2 Data Generation - Model: $MODEL"
echo "=========================================="
echo "Target: $TARGET_DIR"
if [ ${#DOMAIN_ARGS[@]} -gt 0 ]; then
    echo "Domains: ${DOMAIN_ARGS[@]}"
else
    echo "Domains: All"
fi
if [ -n "$SKIP_RENDER" ]; then
    echo "Skip Render: Yes"
else
    echo "Skip Render: No"
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
if [ -n "$STREAM" ]; then
    echo "Stream: Yes"
else
    echo "Stream: No (default)"
fi
echo "Log: $LOG_FILE"
echo "=========================================="

# Step 1: Check for existing instructions and question sets (ground truth prepared by run_task2_prepare_ground_truth.sh)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 1: Checking for existing instructions and question sets..."
INSTRUCTION_COUNT=0
QUESTION_SET_COUNT=0
for domain_dir in "$TARGET_DIR"/domain_*; do
    if [ -d "$domain_dir" ]; then
        for sample_dir in "$domain_dir"/sample_*; do
            if [ -d "$sample_dir/instructions" ] && [ "$(find "$sample_dir/instructions" -type d -name 'inst_*' | wc -l)" -gt 0 ]; then
                INSTRUCTION_COUNT=$((INSTRUCTION_COUNT + 1))
            fi
            if [ -f "$sample_dir/question_set.json" ]; then
                QUESTION_SET_COUNT=$((QUESTION_SET_COUNT + 1))
            fi
        done
    fi
done

if [ $INSTRUCTION_COUNT -eq 0 ] || [ $QUESTION_SET_COUNT -eq 0 ]; then
    echo "WARNING: Instructions or question sets not found."
    echo "Please run ./run_task2_prepare_ground_truth.sh first to generate them."
    echo "Continuing anyway (model editing will skip samples without instructions)..."
else
    echo "Found instructions in $INSTRUCTION_COUNT samples and question sets in $QUESTION_SET_COUNT samples."
    echo "They will be loaded automatically."
fi

# Step 2: Model editing (this is where you change the model)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 2: Running model editing with $MODEL..."

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

# Run model editing
if [ -n "$ENV_VARS" ]; then
    eval $ENV_VARS python scripts/task2/model_editing.py process-all \
        --source "$TARGET_DIR" \
        --output "$TARGET_DIR" \
        --models "$MODEL" \
        "${DOMAIN_ARGS[@]}" \
        $SKIP_RENDER \
        $STREAM \
        >> "$LOG_FILE" 2>&1
else
    python scripts/task2/model_editing.py process-all \
        --source "$TARGET_DIR" \
        --output "$TARGET_DIR" \
        --models "$MODEL" \
        "${DOMAIN_ARGS[@]}" \
        $SKIP_RENDER \
        $STREAM \
        >> "$LOG_FILE" 2>&1
fi

if [ $? -ne 0 ]; then
    echo "ERROR: Step 2 failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 2 completed."

# Step 3: Export dataset.json
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 3: Exporting dataset.json..."
python scripts/task2/export_dataset_json.py \
    --source "$TARGET_DIR" \
    --output "$TARGET_DIR/dataset.json" \
    "${DOMAIN_ARGS[@]}" \
    >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Step 3 failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 3 completed."

echo "=========================================="
echo "Task 2 Data Generation Completed!"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Uncomment the line below to pause before script exits:
# read -p "Press Enter to exit..."

# Instructions for changing model:
# ==========================================
# To change the model, you can either:
# 1. Pass model name as argument:
#    ./run_task2_data_generation.sh your-model-name
#
# 2. Modify the MODEL variable on line 11:
#    MODEL="${1:-your-model-name}"
#
# 3. Set environment variable:
#    MODEL=your-model-name ./run_task2_data_generation.sh
#
# Note: The model is used in Step 2 (model editing).
# Instructions and question sets should be prepared in advance using run_task2_prepare_ground_truth.sh
#
# Common model names:
# - gemini-3-pro-preview
# - gpt-4o
# - claude-3-5-sonnet-20241022
#
# To specify API key and URL (for gemini, gpt, claude):
# 1. Pass --api-key and --api-url as arguments:
#    ./run_task2_data_generation.sh gemini-3-pro-preview --api-key YOUR_KEY --api-url https://api.example.com
#    (If not specified, will use values from .env file)
#
# ==========================================
# Background Execution and Process Management:
# ==========================================
# To run in background:
#   nohup ./run_task2_data_generation.sh [model_name] > /dev/null 2>&1 &
#
# To check if script is running:
#   ps aux | grep "run_task2_data_generation.sh"
#   ps aux | grep "python.*task2"
#
# To stop the background process:
#   1. Find the process ID (PID):
#      ps aux | grep "run_task2_data_generation.sh" | grep -v grep
#   2. Kill the process:
#      kill <PID>
#   Or kill all related processes:
#      pkill -f "run_task2_data_generation.sh"
#      pkill -f "python.*task2"
#
# To monitor the log file in real-time:
#   tail -f "$LOG_FILE"
#
# To check the last few lines of the log:
#   tail -n 50 "$LOG_FILE"
# ==========================================

