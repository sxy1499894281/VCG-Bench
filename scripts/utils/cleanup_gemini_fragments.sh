#!/bin/bash
# Cleanup script for gemini-3-pro-preview fragment files
# Problem: sample_key doesn't include domain, causing conflicts between domains
# Solution: Remove incomplete fragment files (keep architecture which is complete)

set -e

FRAGMENTS_DIR="data/task1_evaluation/fragments"
MODEL="gemini-3-pro-preview"

echo "=========================================="
echo "Gemini Fragment Files Cleanup Script"
echo "=========================================="
echo "Model: $MODEL"
echo "Fragments dir: $FRAGMENTS_DIR"
echo ""

# Backup first
BACKUP_DIR="${FRAGMENTS_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp "$FRAGMENTS_DIR"/${MODEL}_* "$BACKUP_DIR"/ 2>/dev/null || true
echo "✓ Backup created"
echo ""

# Show current status
echo "Current status:"
for file in "$FRAGMENTS_DIR"/${MODEL}_domain_*_results.json; do
    if [ -f "$file" ]; then
        count=$(jq '.samples | length' "$file" 2>/dev/null || echo "0")
        basename=$(basename "$file")
        echo "  $basename: $count samples"
    fi
done
echo ""

# Delete incomplete fragment files (keep only architecture which has 234 samples)
echo "Deleting incomplete fragment files..."
deleted=0
for file in "$FRAGMENTS_DIR"/${MODEL}_domain_*_results.json; do
    if [ -f "$file" ]; then
        count=$(jq '.samples | length' "$file" 2>/dev/null || echo "0")
        # Keep architecture (234 samples), delete others
        if [[ ! "$file" =~ "architecture" ]] || [ "$count" -lt 234 ]; then
            echo "  Deleting $(basename "$file") ($count samples)"
            rm "$file"
            ((deleted++))
        else
            echo "  Keeping $(basename "$file") ($count samples - complete)"
        fi
    fi
done

echo ""
echo "=========================================="
echo "Cleanup completed!"
echo "Deleted: $deleted files"
echo "Backup: $BACKUP_DIR"
echo "=========================================="
echo ""
echo "Next step: Run evaluation to process missing samples"
echo "  ./scripts/commands/task1_evaluate.sh gemini-3-pro-preview --disable-metrics siglip_score"
echo ""
