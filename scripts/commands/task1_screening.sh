#!/bin/bash
# Task 1 Screening Script - Manual Quality Filtering for Task 2 Ground Truth
# Usage: ./run_task1_screening.sh [command] [options]
# ./run_task1_screening.sh review
# ./run_task1_screening.sh extract

# Commands:
#   review    - Start interactive review (default)
#   status    - Show screening status
#   extract   - Extract approved samples to task2_benchmark

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
SOURCE_DIR="${SOURCE_DIR:-data/task1_benchmark}"
TARGET_DIR="${TARGET_DIR:-data/task2_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task1_screening_${TIMESTAMP}.log"

# Default command
COMMAND="${1:-review}"

echo "=========================================="
echo "Task 1 Screening - Manual Quality Filtering"
echo "=========================================="
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"
echo "Command: $COMMAND"
echo "Log: $LOG_FILE"
echo "=========================================="

case "$COMMAND" in
    review)
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting web review interface..."
        echo ""
        
        # Check if Flask is installed
        if ! python -c "import flask" 2>/dev/null; then
            echo "ERROR: Flask is not installed!"
            echo ""
            echo "Please install Flask to use the web interface:"
            echo "  pip install flask"
            echo ""
            echo "Or use CLI mode instead:"
            echo "  python scripts/task1/filter.py review --source \"$SOURCE_DIR\" --cli"
            exit 1
        fi
        
        echo "The web interface will open automatically in your browser."
        echo "If it doesn't open, navigate to the URL shown below."
        echo ""
        echo "Instructions:"
        echo "  - Use the web interface to review and mark samples"
        echo "  - Press Ctrl+C to stop the server"
        echo ""
        echo "Note: If you prefer CLI mode, modify the script to add --cli flag"
        echo ""
        
        python scripts/task1/filter.py review \
            --source "$SOURCE_DIR" \
            >> "$LOG_FILE" 2>&1
        
        if [ $? -ne 0 ]; then
            echo "ERROR: Review failed. Check log: $LOG_FILE"
            exit 1
        fi
        
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Review completed."
        ;;
    
    status)
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Checking screening status..."
        python scripts/task1/filter.py status \
            --source "$SOURCE_DIR" \
            >> "$LOG_FILE" 2>&1
        
        if [ $? -ne 0 ]; then
            echo "ERROR: Status check failed. Check log: $LOG_FILE"
            exit 1
        fi
        ;;
    
    extract)
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Extracting approved samples to task2_benchmark..."
        echo ""
        echo "This will copy all approved Gemini samples from task1_benchmark to task2_benchmark."
        echo "Only samples marked as 'approved' will be extracted."
        echo ""
        read -p "Continue? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            echo "Extraction cancelled."
            exit 0
        fi
        
        python scripts/data_preparation/prepare_benchmark.py \
            --source "$SOURCE_DIR" \
            --target "$TARGET_DIR" \
            >> "$LOG_FILE" 2>&1
        
        if [ $? -ne 0 ]; then
            echo "ERROR: Extraction failed. Check log: $LOG_FILE"
            exit 1
        fi
        
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Extraction completed."
        echo "Approved samples extracted to: $TARGET_DIR"
        ;;
    
    *)
        echo "Unknown command: $COMMAND"
        echo ""
        echo "Usage: ./run_task1_screening.sh [command]"
        echo ""
        echo "Commands:"
        echo "  review  - Start interactive review (default)"
        echo "  status  - Show screening status"
        echo "  extract - Extract approved samples to task2_benchmark"
        echo ""
        echo "Examples:"
        echo "  ./run_task1_screening.sh review"
        echo "  ./run_task1_screening.sh status"
        echo "  ./run_task1_screening.sh extract"
        exit 1
        ;;
esac

echo "=========================================="
echo "Screening operation completed!"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Instructions:
# ==========================================
# Workflow:
# 1. Run task1 data generation:
#    ./run_task1_data_generation.sh gemini-3-pro-preview
#
# 2. Review and filter samples:
#    ./run_task1_screening.sh review
#    - This opens a web interface in your browser (default)
#    - Use the web interface to review and mark samples
#    - Progress is saved automatically
#    - If port 5000 is in use, it will automatically try other ports
#    - For CLI mode, modify the script to add --cli flag
#
# 3. Check screening status:
#    ./run_task1_screening.sh status
#    - Shows how many samples are approved/rejected/pending
#
# 4. Extract approved samples to task2_benchmark:
#    ./run_task1_screening.sh extract
#    - Copies all approved samples to task2_benchmark
#    - This is the ground truth for task2
#
# 5. Continue with task2 data generation:
#    ./run_task2_data_generation.sh gemini-3-pro-preview
#
# Troubleshooting:
# - If you see "No module named 'flask'": Install Flask with: pip install flask
#   The script will automatically check for Flask before starting
# - If port 5000 is in use: The script will automatically try other ports (5001, 5002, etc.)
#   Or disable AirPlay Receiver on macOS: System Settings > General > AirDrop & Handoff
#
# Tips:
# - You can run 'review' multiple times to continue where you left off
# - Use 'status' to check progress anytime
# - Only run 'extract' after you've reviewed all samples
# ==========================================

