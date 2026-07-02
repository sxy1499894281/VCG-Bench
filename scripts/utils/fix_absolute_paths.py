#!/usr/bin/env python3
"""
修复评估结果文件中的绝对路径为相对路径
将 task1_evaluation/fragments 目录下的所有 JSON 文件中的绝对路径转换为相对路径
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

def get_relative_path(path_str: str) -> str:
    """
    将绝对路径转换为相对路径（从task1_benchmark开始）
    
    Args:
        path_str: 绝对路径字符串
        
    Returns:
        相对路径字符串（从task1_benchmark开始）
    """
    if not path_str or not isinstance(path_str, str):
        return path_str
    
    # 查找task1_benchmark在路径中的位置
    benchmark_marker = "task1_benchmark"
    if benchmark_marker in path_str:
        # 找到task1_benchmark目录的位置
        parts = Path(path_str).parts
        try:
            benchmark_idx = parts.index(benchmark_marker)
            # 相对路径从task1_benchmark开始
            rel_parts = parts[benchmark_idx:]
            return str(Path(*rel_parts))
        except (ValueError, IndexError):
            pass
    
    # 如果找不到task1_benchmark，返回原始路径
    return path_str

def fix_paths_in_metric_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    修复指标details中的路径
    
    Args:
        details: 指标details字典
        
    Returns:
        修复后的details字典
    """
    if not isinstance(details, dict):
        return details
    
    fixed_details = details.copy()
    
    # 修复original_image和generated_image路径
    if "original_image" in fixed_details:
        fixed_details["original_image"] = get_relative_path(fixed_details["original_image"])
    
    if "generated_image" in fixed_details:
        fixed_details["generated_image"] = get_relative_path(fixed_details["generated_image"])
    
    return fixed_details

def fix_paths_in_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    """
    修复样本中的路径
    
    Args:
        sample: 样本字典
        
    Returns:
        修复后的样本字典
    """
    if not isinstance(sample, dict):
        return sample
    
    fixed_sample = sample.copy()
    
    # 修复metrics中的路径
    if "metrics" in fixed_sample and isinstance(fixed_sample["metrics"], dict):
        fixed_metrics = {}
        for metric_name, metric_result in fixed_sample["metrics"].items():
            if isinstance(metric_result, dict):
                fixed_metric = metric_result.copy()
                if "details" in fixed_metric:
                    fixed_metric["details"] = fix_paths_in_metric_details(fixed_metric["details"])
                fixed_metrics[metric_name] = fixed_metric
            else:
                fixed_metrics[metric_name] = metric_result
        fixed_sample["metrics"] = fixed_metrics
    
    return fixed_sample

def fix_paths_in_file(file_path: Path) -> bool:
    """
    修复单个文件中的路径
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        是否进行了修改
    """
    try:
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        
        # 修复samples中的路径
        if "samples" in data and isinstance(data["samples"], list):
            fixed_samples = []
            for sample in data["samples"]:
                fixed_sample = fix_paths_in_sample(sample)
                if fixed_sample != sample:
                    modified = True
                fixed_samples.append(fixed_sample)
            data["samples"] = fixed_samples
        
        # 如果进行了修改，保存文件
        if modified:
            # 备份原文件
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            if not backup_path.exists():
                import shutil
                shutil.copy2(file_path, backup_path)
            
            # 保存修复后的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False

def main():
    """主函数"""
    fragments_dir = Path(__file__).parent.parent / "data" / "task1_evaluation" / "fragments"
    
    if not fragments_dir.exists():
        print(f"Error: Fragments directory not found: {fragments_dir}")
        return 1
    
    # 获取所有JSON文件
    json_files = list(fragments_dir.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {fragments_dir}")
        return 0
    
    print(f"Found {len(json_files)} JSON files")
    print(f"Processing files in {fragments_dir}...")
    
    modified_count = 0
    for json_file in json_files:
        if json_file.name.endswith('.bak'):
            continue
        
        if fix_paths_in_file(json_file):
            modified_count += 1
            print(f"  ✓ Fixed: {json_file.name}")
        else:
            print(f"  - No changes: {json_file.name}")
    
    print(f"\nDone! Modified {modified_count} files out of {len(json_files)} total files.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

