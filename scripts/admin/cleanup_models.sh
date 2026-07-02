#!/bin/bash
# 清理指定模型的数据和日志
# 用法: 
#   ./cleanup_models.sh          # 查看可删除的内容
#   ./cleanup_models.sh execute   # 执行删除（会再次确认）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 要保留的模型（不删除）
KEEP_MODELS=("gemini-3-pro-preview" "gemini-3-flash-preview" "GLM-4.6V" "Qwen3-VL-8B-Instruct" "Qwen3-VL-32B-Instruct" "Qwen3-VL-235B-A22B-Instruct" "Qwen3-Omni-30B-A3B-Instruct" "step3" "claude-opus-4-5-20251101" "claude-sonnet-4-5-20250929" "internvl3-14b" "internvl3-38b")

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}模型数据清理工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 查找所有模型目录
echo -e "${CYAN}[1] 数据目录 (data/task1_benchmark/.../model_*)${NC}"
echo "----------------------------------------"

# 使用临时文件存储模型信息（兼容 bash 3.2 和 zsh）
MODEL_INFO_FILE=$(mktemp)
# 确保脚本退出时清理临时文件
trap "rm -f \"$MODEL_INFO_FILE\"" EXIT INT TERM
total_dirs=0
total_size=0

while IFS= read -r dir; do
    model_name=$(basename "$dir" | sed 's/model_//')
    
    # 检查是否在保留列表中
    should_keep=false
    for keep in "${KEEP_MODELS[@]}"; do
        # 处理带斜杠的模型名（如 zai-org/GLM-4.6V）
        # 实际目录结构是: model_zai-org/GLM-4.6V/
        if [[ "$keep" == *"/"* ]]; then
            # 提取斜杠前后的部分
            keep_prefix=$(echo "$keep" | cut -d'/' -f1)
            keep_suffix=$(echo "$keep" | cut -d'/' -f2)
            # 检查目录是否匹配: model_前缀/后缀
            if [[ "$model_name" == "$keep_prefix" ]] && [[ -d "$dir/$keep_suffix" ]]; then
                should_keep=true
                break
            fi
        fi
        # 普通模型名匹配
        if [[ "$model_name" == "$keep" ]] || [[ "$dir" == *"model_$keep"* ]]; then
            should_keep=true
            break
        fi
    done
    
    if [ "$should_keep" = false ]; then
        size=$(du -sk "$dir" 2>/dev/null | cut -f1)
        total_size=$((total_size + size))
        total_dirs=$((total_dirs + 1))
        
        # 提取领域和样本信息
        domain_sample=$(echo "$dir" | sed 's|data/task1_benchmark/||' | sed 's|/model_.*||')
        echo "$model_name|$domain_sample" >> "$MODEL_INFO_FILE"
    fi
done < <(find data/task1_benchmark -type d -name "model_*" 2>/dev/null)

# 统计模型数量和生成列表
if [ ! -s "$MODEL_INFO_FILE" ]; then
    echo -e "${GREEN}✓ 没有需要删除的模型目录${NC}"
else
    # 统计每个模型的目录数
    model_count=$(cut -d'|' -f1 "$MODEL_INFO_FILE" | sort -u | wc -l | tr -d ' ')
    echo -e "${YELLOW}找到 $model_count 个不同的模型，共 $total_dirs 个目录${NC}"
    echo -e "${YELLOW}总大小: $(numfmt --to=iec-i --suffix=B $((total_size * 1024)) 2>/dev/null || echo "${total_size}KB")${NC}"
    echo ""
    echo "模型列表:"
    for model in $(cut -d'|' -f1 "$MODEL_INFO_FILE" | sort -u); do
        count=$(grep -c "^$model|" "$MODEL_INFO_FILE" || echo 0)
        echo -e "  ${RED}☐${NC} $model (约 $count 个样本目录)"
    done
fi

echo ""
echo ""

# 2. 查找日志文件
echo -e "${CYAN}[2] 日志文件 (logs/task1_data_generation_*.log)${NC}"
echo "----------------------------------------"

declare -a log_files
total_log_size=0

while IFS= read -r log_file; do
    # 提取模型名
    model_name=$(basename "$log_file" | sed 's/task1_data_generation_//' | sed 's/_[0-9]\{8\}_[0-9]\{6\}\.log$//')
    
    # 检查是否在保留列表中
    should_keep=false
    for keep in "${KEEP_MODELS[@]}"; do
        keep_sanitized=$(echo "$keep" | sed 's/\//_/g')
        # 日志文件名使用 sanitized 版本（斜杠替换为下划线）
        # 例如: zai-org/GLM-4.6V -> zai-org_GLM-4.6V
        if [[ "$model_name" == "$keep_sanitized" ]] || [[ "$log_file" == *"$keep_sanitized"* ]]; then
            should_keep=true
            break
        fi
    done
    
    if [ "$should_keep" = false ]; then
        size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
        total_log_size=$((total_log_size + size))
        log_files+=("$log_file")
    fi
done < <(find logs -name "task1_data_generation_*.log" 2>/dev/null)

if [ ${#log_files[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ 没有需要删除的日志文件${NC}"
else
    echo -e "${YELLOW}找到 ${#log_files[@]} 个日志文件${NC}"
    echo -e "${YELLOW}总大小: $(numfmt --to=iec-i --suffix=B $total_log_size 2>/dev/null || echo "${total_log_size}B")${NC}"
    echo ""
    echo "日志文件列表:"
    for log_file in "${log_files[@]}"; do
        size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
        size_human=$(numfmt --to=iec-i --suffix=B $size 2>/dev/null || echo "${size}B")
        echo -e "  ${RED}☐${NC} $log_file ($size_human)"
    done
fi

echo ""
echo ""

# 3. 生成清理脚本
echo -e "${CYAN}[3] 清理操作${NC}"
echo "----------------------------------------"
echo ""
echo -e "${YELLOW}可删除的内容列表:${NC}"
echo ""
echo -e "${BLUE}数据目录:${NC}"
if [ -f "$MODEL_INFO_FILE" ] && [ -s "$MODEL_INFO_FILE" ]; then
    for model in $(cut -d'|' -f1 "$MODEL_INFO_FILE" | sort -u); do
        echo -e "  ☐ $model"
    done
fi
echo ""
echo -e "${BLUE}日志文件:${NC}"
for log_file in "${log_files[@]}"; do
    echo -e "  ☐ $log_file"
done
echo ""
echo -e "${GREEN}使用方法:${NC}"
echo "  1. 查看列表: ./cleanup_models.sh"
echo "  2. 执行删除: ./cleanup_models.sh execute"
echo ""
echo -e "${RED}警告: 删除操作不可恢复！${NC}"
echo ""

# 如果提供了 execute 参数，执行清理
if [ "$1" == "execute" ]; then
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}执行清理操作${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    model_count=0
    if [ -f "$MODEL_INFO_FILE" ] && [ -s "$MODEL_INFO_FILE" ]; then
        model_count=$(cut -d'|' -f1 "$MODEL_INFO_FILE" | sort -u | wc -l | tr -d ' ')
    fi
    echo -e "${YELLOW}将要删除:${NC}"
    echo -e "${YELLOW}  - $model_count 个模型的数据目录（共 $total_dirs 个目录）${NC}"
    echo -e "${YELLOW}  - ${#log_files[@]} 个日志文件${NC}"
    echo ""
    echo -e "${RED}请仔细确认以上内容！${NC}"
    echo ""
    read -p "确认删除？输入 'yes' 继续，其他任何内容将取消: " confirm
    if [ "$confirm" != "yes" ]; then
        echo -e "${YELLOW}已取消删除操作${NC}"
        rm -f "$MODEL_INFO_FILE"
        exit 0
    fi
    
    echo ""
    echo -e "${YELLOW}正在删除...${NC}"
    
    # 删除模型目录
    deleted_dirs=0
    if [ -f "$MODEL_INFO_FILE" ] && [ -s "$MODEL_INFO_FILE" ]; then
        for model in $(cut -d'|' -f1 "$MODEL_INFO_FILE" | sort -u); do
            echo -e "${BLUE}删除模型目录: $model${NC}"
            find data/task1_benchmark -type d -name "model_$model" -exec rm -rf {} + 2>/dev/null && deleted_dirs=$((deleted_dirs + 1)) || true
        done
    fi
    
    # 删除日志文件
    deleted_logs=0
    for log_file in "${log_files[@]}"; do
        echo -e "${BLUE}删除日志: $(basename $log_file)${NC}"
        rm -f "$log_file" && deleted_logs=$((deleted_logs + 1)) || true
    done
    
    echo ""
    echo -e "${GREEN}✓ 清理完成${NC}"
    echo -e "${GREEN}  删除了 $deleted_dirs 个模型目录${NC}"
    echo -e "${GREEN}  删除了 $deleted_logs 个日志文件${NC}"
fi

# 清理临时文件
rm -f "$MODEL_INFO_FILE"
