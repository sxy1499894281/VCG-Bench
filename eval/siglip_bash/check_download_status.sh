#!/bin/bash
# 检查 SigLIP 模型下载状态
# Usage: ./scripts/check_download_status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/download_siglip_model.log"

echo "=========================================="
echo "SigLIP 模型下载状态检查"
echo "=========================================="

# 1. 检查进程是否在运行
echo ""
echo "1️⃣ 进程状态:"
PROCESS=$(ps aux | grep "download_siglip_model.py" | grep -v grep)
if [ -n "$PROCESS" ]; then
    PID=$(echo $PROCESS | awk '{print $2}')
    CPU=$(echo $PROCESS | awk '{print $3}')
    MEM=$(echo $PROCESS | awk '{print $4}')
    TIME=$(echo $PROCESS | awk '{print $10}')
    echo "   ✅ 进程正在运行"
    echo "   - 进程 ID (PID): $PID"
    echo "   - CPU 使用率: ${CPU}%"
    echo "   - 内存使用率: ${MEM}%"
    echo "   - 运行时间: $TIME"
    echo ""
    echo "   停止下载: kill $PID"
else
    echo "   ❌ 进程未运行"
fi

# 2. 检查日志文件
echo ""
echo "2️⃣ 日志文件状态:"
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -l < "$LOG_FILE")
    LOG_BYTES=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null)
    LOG_MTIME=$(stat -f%Sm "$LOG_FILE" 2>/dev/null || stat -c%y "$LOG_FILE" 2>/dev/null | cut -d'.' -f1)
    
    echo "   ✅ 日志文件存在: $LOG_FILE"
    echo "   - 文件大小: ${LOG_BYTES} 字节"
    echo "   - 行数: $LOG_SIZE 行"
    echo "   - 最后修改: $LOG_MTIME"
else
    echo "   ⚠️  日志文件不存在"
fi

# 3. 检查日志内容（最后几行）
echo ""
echo "3️⃣ 最新日志内容 (最后 10 行):"
echo "   ----------------------------------------"
if [ -f "$LOG_FILE" ]; then
    tail -n 10 "$LOG_FILE" | sed 's/^/   /'
else
    echo "   (日志文件不存在)"
fi
echo "   ----------------------------------------"

# 4. 检查是否下载成功
echo ""
echo "4️⃣ 下载状态判断:"
if [ -f "$LOG_FILE" ]; then
    if grep -q "✅ 模型下载完成" "$LOG_FILE"; then
        echo "   ✅ 下载已完成！"
        echo ""
        echo "   模型信息:"
        grep -A 5 "✅ 模型下载完成" "$LOG_FILE" | sed 's/^/   /'
    elif grep -q "❌" "$LOG_FILE"; then
        echo "   ❌ 下载失败"
        echo ""
        echo "   错误信息:"
        grep "❌" "$LOG_FILE" | sed 's/^/   /'
    elif [ -n "$PROCESS" ]; then
        echo "   ⏳ 下载进行中..."
        echo "   提示: 模型较大，下载可能需要一些时间"
        echo "   建议: 使用 'tail -f $LOG_FILE' 实时查看进度"
    else
        echo "   ⚠️  状态未知"
    fi
else
    echo "   ⚠️  无法判断（日志文件不存在）"
fi

# 5. 检查模型缓存目录
echo ""
echo "5️⃣ 模型缓存目录:"
CACHE_DIR="$HOME/.cache/huggingface/transformers"
if [ -d "$CACHE_DIR" ]; then
    echo "   ✅ 缓存目录存在: $CACHE_DIR"
    # 查找 siglip 相关文件
    SIGLIP_FILES=$(find "$CACHE_DIR" -name "*siglip*" -type f 2>/dev/null | head -5)
    if [ -n "$SIGLIP_FILES" ]; then
        echo "   ✅ 找到 SigLIP 相关文件:"
        echo "$SIGLIP_FILES" | sed 's/^/      /'
    else
        echo "   ⚠️  未找到 SigLIP 相关文件（可能还在下载中）"
    fi
else
    echo "   ⚠️  缓存目录不存在: $CACHE_DIR"
fi

echo ""
echo "=========================================="
echo "💡 常用命令:"
echo "   实时查看日志: tail -f $LOG_FILE"
echo "   查看完整日志: cat $LOG_FILE"
echo "   停止下载: kill <PID>"
echo "=========================================="

