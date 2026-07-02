#!/bin/bash
# Task 2 Viewer Script - View and Edit Task 2 Data
# Usage: ./run_task2_viewer.sh [command] [options]
# ./run_task2_viewer.sh review
# ./run_task2_viewer.sh status

# Commands:
#   review    - Start interactive review (default)
#   status    - Show viewing status

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
SOURCE_DIR="${SOURCE_DIR:-data/task2_benchmark}"
EVALUATION_DIR="${EVALUATION_DIR:-data/task2_evaluation}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task2_viewer_${TIMESTAMP}.log"

# Default command
COMMAND="${1:-review}"

echo "=========================================="
echo "Task 2 Viewer - View and Edit Task 2 Data"
echo "=========================================="
echo "Source: $SOURCE_DIR"
echo "Evaluation: $EVALUATION_DIR"
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
            exit 1
        fi
        
        echo "The web interface will open automatically in your browser."
        echo "If it doesn't open, navigate to the URL shown below."
        echo ""
        echo "Instructions:"
        echo "  - Use the web interface to view task2 data"
        echo "  - View render.png, instructions, modified XML renderings"
        echo "  - View xdrfr and scs metric scores"
        echo "  - Edit xdrfr question answers and view modification history"
        echo "  - Press Ctrl+C to stop the server"
        echo ""
        
        python scripts/task2/viewer.py review \
            --source "$SOURCE_DIR" \
            --evaluation "$EVALUATION_DIR" \
            >> "$LOG_FILE" 2>&1
        
        if [ $? -ne 0 ]; then
            echo "ERROR: Review failed. Check log: $LOG_FILE"
            exit 1
        fi
        
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Review completed."
        ;;
    
    status)
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Checking viewing status..."
        python scripts/task2/viewer.py status \
            --source "$SOURCE_DIR" \
            >> "$LOG_FILE" 2>&1
        
        if [ $? -ne 0 ]; then
            echo "ERROR: Status check failed. Check log: $LOG_FILE"
            exit 1
        fi
        ;;
    
    *)
        echo "Unknown command: $COMMAND"
        echo ""
        echo "Usage: ./run_task2_viewer.sh [command]"
        echo ""
        echo "Commands:"
        echo "  review  - Start interactive review (default)"
        echo "  status  - Show viewing status"
        echo ""
        echo "Examples:"
        echo "  ./run_task2_viewer.sh review"
        echo "  ./run_task2_viewer.sh status"
        exit 1
        ;;
esac

echo "=========================================="
echo "Viewer operation completed!"
echo "Log file: $LOG_FILE"
echo "=========================================="

# Instructions:
# ==========================================
# Workflow:
# 1. Run task2 data generation:
#    ./run_task2_data_generation.sh gemini-3-pro-preview
#
# 2. View and edit task2 data:
#    ./run_task2_viewer.sh review
#    - This opens a web interface in your browser (default)
#    - View render.png, instructions (with difficulty switching)
#    - View modified XML renderings (with model switching)
#    - View xdrfr and scs metric scores
#    - Edit xdrfr question answers and view modification history
#    - Filter to view only manually modified instructions
#    - Press Ctrl+C to stop the server
#
# 3. Check viewing status:
#    ./run_task2_viewer.sh status
#    - Shows how many samples/instructions are available
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
# - Manual edits to xdrfr answers are saved automatically
# ==========================================

