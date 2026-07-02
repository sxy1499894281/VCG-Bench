#!/usr/bin/env python3
"""
修复 Task2 评估结果文件中的绝对路径问题
将所有绝对路径转换为相对路径（相对于 task2_benchmark 目录）
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_relative_path(path_str: str) -> str:
    """
    将绝对路径转换为相对路径（相对于包含task2_benchmark的目录）
    
    Args:
        path_str: 绝对路径字符串
        
    Returns:
        相对路径字符串
    """
    if not path_str or not isinstance(path_str, str):
        return path_str
    
    # 查找task2_benchmark在路径中的位置
    benchmark_marker = "task2_benchmark"
    if benchmark_marker in path_str:
        # 找到task2_benchmark目录
        try:
            parts = Path(path_str).parts
            benchmark_idx = parts.index(benchmark_marker)
            # 相对路径从task2_benchmark开始
            rel_parts = parts[benchmark_idx:]
            return str(Path(*rel_parts))
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to convert path {path_str}: {e}")
            return path_str
    
    # 如果找不到task2_benchmark，返回原始路径
    return path_str


def is_absolute_path(path_str: str) -> bool:
    """检查字符串是否是绝对路径"""
    if not path_str or not isinstance(path_str, str):
        return False
    
    # 检查是否是绝对路径（Unix/Mac 或 Windows）
    if path_str.startswith('/') or (len(path_str) > 1 and path_str[1] == ':'):
        # 检查是否包含常见的绝对路径模式
        if '/Users/' in path_str or '/home/' in path_str or 'C:\\' in path_str or 'D:\\' in path_str:
            return True
    
    return False


def fix_paths_in_dict(obj: Any, depth: int = 0) -> Any:
    """
    递归修复字典/列表中的绝对路径
    
    Args:
        obj: 要处理的对象（字典、列表或基本类型）
        depth: 递归深度（用于防止无限递归）
        
    Returns:
        修复后的对象
    """
    if depth > 20:  # 防止无限递归
        return obj
    
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key == "json_path" and isinstance(value, str) and is_absolute_path(value):
                # 专门处理 json_path 字段
                result[key] = get_relative_path(value)
                logger.debug(f"Fixed json_path: {value[:80]}... -> {result[key]}")
            elif isinstance(value, str) and is_absolute_path(value):
                # 检查是否是路径字段（包含 path 关键字）
                if 'path' in key.lower():
                    result[key] = get_relative_path(value)
                    logger.debug(f"Fixed {key}: {value[:80]}... -> {result[key]}")
                else:
                    result[key] = value
            else:
                # 递归处理嵌套结构
                result[key] = fix_paths_in_dict(value, depth + 1)
        return result
    elif isinstance(obj, list):
        return [fix_paths_in_dict(item, depth + 1) for item in obj]
    else:
        return obj


def fix_json_file(json_file: Path) -> bool:
    """
    修复单个 JSON 文件中的绝对路径
    
    Args:
        json_file: JSON 文件路径
        
    Returns:
        是否成功修复
    """
    try:
        # 读取文件
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查是否包含绝对路径
        data_str = json.dumps(data)
        if not is_absolute_path(data_str) and '/Users/' not in data_str and '/home/' not in data_str:
            logger.debug(f"{json_file.name}: No absolute paths found, skipping")
            return False
        
        # 修复路径
        fixed_data = fix_paths_in_dict(data)
        
        # 检查是否有变化
        if json.dumps(fixed_data, sort_keys=True) == json.dumps(data, sort_keys=True):
            logger.debug(f"{json_file.name}: No changes needed")
            return False
        
        # 备份原文件
        backup_file = json_file.with_suffix('.json.bak')
        if not backup_file.exists():
            import shutil
            shutil.copy2(json_file, backup_file)
            logger.info(f"Created backup: {backup_file.name}")
        
        # 保存修复后的文件
        temp_file = json_file.with_suffix('.json.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, indent=2, ensure_ascii=False)
        
        # 原子替换
        temp_file.replace(json_file)
        logger.info(f"Fixed: {json_file.name}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing {json_file.name}: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    fragments_dir = Path('data/task2_evaluation/fragments')
    
    if not fragments_dir.exists():
        logger.error(f"Directory not found: {fragments_dir}")
        return
    
    # 查找所有 JSON 文件
    json_files = list(fragments_dir.glob('*.json'))
    json_files = [f for f in json_files if not f.name.endswith('.bak')]
    
    logger.info(f"Found {len(json_files)} JSON files to process")
    
    # 处理每个文件
    fixed_count = 0
    for json_file in json_files:
        if fix_json_file(json_file):
            fixed_count += 1
    
    logger.info(f"Fixed {fixed_count} out of {len(json_files)} files")
    
    # 清理备份文件（可选）
    backup_files = list(fragments_dir.glob('*.bak'))
    if backup_files:
        logger.info(f"Backup files created: {len(backup_files)}")
        logger.info("You can delete .bak files after verifying the fixes")


if __name__ == '__main__':
    main()

