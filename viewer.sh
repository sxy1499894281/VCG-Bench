#!/bin/bash
# Unified Data Viewer / Screening Script
#
# Usage:
#   ./viewer.sh task1 review             - Task 1 interactive screening (web UI)
#   ./viewer.sh task1 status             - Task 1 screening progress
#   ./viewer.sh task1 extract            - Extract approved samples to task2_benchmark
#   ./viewer.sh task2 review             - Task 2 interactive viewer (web UI)
#   ./viewer.sh task2 status             - Task 2 viewer status

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TASK="${1:-}"
COMMAND="${2:-review}"

usage() {
    echo "Usage: ./viewer.sh [task] [command]"
    echo ""
    echo "Tasks:"
    echo "  task1   - Screen task1 samples for quality filtering"
    echo "  task2   - View and edit task2 data and evaluation results"
    echo ""
    echo "Commands for task1:"
    echo "  review    - Start interactive web review (default)"
    echo "  status    - Show screening progress"
    echo "  extract   - Extract approved samples to task2_benchmark"
    echo ""
    echo "Commands for task2:"
    echo "  review    - Start interactive web viewer (default)"
    echo "  status    - Show viewer status"
    echo ""
    echo "Examples:"
    echo "  ./viewer.sh task1 review"
    echo "  ./viewer.sh task1 status"
    echo "  ./viewer.sh task1 extract"
    echo "  ./viewer.sh task2 review"
    echo "  ./viewer.sh task2 status"
}

case "$TASK" in
    task1)
        bash "scripts/commands/task1_screening.sh" "$COMMAND"
        ;;
    task2)
        bash "scripts/commands/task2_viewer.sh" "$COMMAND"
        ;;
    "")
        echo "ERROR: No task specified."
        echo ""
        usage
        exit 1
        ;;
    *)
        echo "ERROR: Unknown task: $TASK"
        echo ""
        usage
        exit 1
        ;;
esac
