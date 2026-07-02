#!/bin/bash
# Task 1 Data Generation Script (Single Model)
# Usage: 
#   Foreground: ./run_task1_data_generation.sh [model_name]
#   Background: nohup ./run_task1_data_generation.sh gemini-3-pro-preview > /dev/null 2>&1 &
# Example: ./run_task1_data_generation.sh gemini-3-pro-preview

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
# Usage: ./run_task1_data_generation.sh [model_name] [--domain domain1 domain2 ...] [--skip-render]
MODEL="${1:-gemini-3-pro-preview}"
shift || true  # Remove first argument (model name)

# Parse remaining arguments for --domain, --skip-render, --api-key, and --api-url
DOMAIN_ARGS=()
SKIP_RENDER=""
API_KEY=""
API_URL=""
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
            API_KEY="$2"
            shift 2
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Configuration (modify these paths as needed)
SOURCE_DIR="${SOURCE_DIR:-data/raw_picture}"
TARGET_DIR="${TARGET_DIR:-data/task1_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file with timestamp
# Sanitize model name for filename (replace / with _)
MODEL_SANITIZED=$(echo "$MODEL" | sed 's/\//_/g')
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task1_data_generation_${MODEL_SANITIZED}_${TIMESTAMP}.log"

echo "=========================================="
echo "Task 1 Data Generation - Model: $MODEL"
echo "=========================================="
echo "Source: $SOURCE_DIR"
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
    echo "API Key: ${API_KEY:0:10}... (set)"
else
    echo "API Key: (using environment variable CUSTOM_API_KEY)"
fi
if [ -n "$API_URL" ]; then
    echo "API URL: $API_URL"
else
    echo "API URL: (using environment variable CUSTOM_BASE_URL)"
fi
echo "Log: $LOG_FILE"
echo "=========================================="

# Step 1: Generate XML and rendered images
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 1: Generating XML and rendered images..."

# Set environment variables if API key/URL are provided
if [ -n "$API_KEY" ]; then
    export CUSTOM_API_KEY="$API_KEY"
fi
if [ -n "$API_URL" ]; then
    export CUSTOM_BASE_URL="$API_URL"
fi

python scripts/task1/generate.py \
    --source "$SOURCE_DIR" \
    --target "$TARGET_DIR" \
    --models "$MODEL" \
    "${DOMAIN_ARGS[@]}" \
    $SKIP_RENDER \
    >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Step 1 failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 1 completed."

# Step 2: Check and load QA pairs (ground truth prepared by run_task1_prepare_ground_truth.sh)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 2: Checking for existing QA pairs..."
QA_COUNT=0
for domain_dir in "$TARGET_DIR"/domain_*; do
    if [ -d "$domain_dir" ]; then
        for sample_dir in "$domain_dir"/sample_*; do
            if [ -f "$sample_dir/qa_pairs.json" ]; then
                QA_COUNT=$((QA_COUNT + 1))
            fi
        done
    fi
done

if [ $QA_COUNT -eq 0 ]; then
    echo "WARNING: No QA pairs found. Please run ./run_task1_prepare_ground_truth.sh first to generate QA pairs."
    echo "Continuing without QA pairs..."
else
    echo "Found QA pairs in $QA_COUNT samples. They will be loaded automatically."
fi

# Step 3: Generate dataset.json (will load QA pairs if available)
# Note: generate_dataset_json is automatically called at the end of process_all_domains in Step 1
# This step ensures it's called and reads QA pairs from qa_pairs.json files if available
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 3: Generating dataset.json (will load QA pairs from qa_pairs.json files if available)..."
python -c "
import sys
from pathlib import Path
project_root = Path('$SCRIPT_DIR')
# Ensure we can import scripts.* by adding project root
sys.path.insert(0, str(project_root))
from scripts.task1.generate import generate_dataset_json
target_dir = Path('$TARGET_DIR')
generate_dataset_json(target_dir, generate_qa=True)
print(f'Dataset JSON generated at: {target_dir / \"dataset.json\"}')
" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "WARNING: Step 3 failed, but dataset.json may have been generated in Step 1. Check log: $LOG_FILE"
    # Don't exit, as dataset.json might already exist from Step 1
else
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 3 completed."
fi

echo "=========================================="
echo "Task 1 Data Generation Completed!"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Uncomment the line below to pause before script exits:
# read -p "Press Enter to exit..."

# Instructions for changing model:
# ==========================================
# To change the model, you can either:
# 1. Pass model name as argument:
#    ./run_task1_data_generation.sh your-model-name
#
# 2. Modify the MODEL variable on line 11:
#    MODEL="${1:-your-model-name}"
#
# 3. Set environment variable:
#    MODEL=your-model-name ./run_task1_data_generation.sh
#
# Common model names:
# - gemini-3-pro-preview
# - gpt-4o
# - claude-3-5-sonnet-20241022
#
# ==========================================
# Background Execution and Process Management:
# ==========================================
# To run in background:
#   nohup ./run_task1_data_generation.sh [model_name] > /dev/null 2>&1 &
#
# To check if script is running:
#   ps aux | grep "run_task1_data_generation.sh"
#   ps aux | grep "python.*generate.py"
#
# To stop the background process:
#   1. Find the process ID (PID):
#      ps aux | grep "run_task1_data_generation.sh" | grep -v grep
#   2. Kill the process:
#      kill <PID>
#   Or kill all related processes:
#      pkill -f "run_task1_data_generation.sh"
#      pkill -f "python.*generate.py"
#
# To monitor the log file in real-time:
#   tail -f "$LOG_FILE"
#
# To check the last few lines of the log:
#   tail -n 50 "$LOG_FILE"
# ==========================================

