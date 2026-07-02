#!/usr/bin/env python3
"""
清理失败的评估指标：将 success=false 且 score=0.0 的记录改为 score=None
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def cleanup_fragment_file(fragment_file: Path) -> tuple[int, int]:
    """
    清理单个分片文件
    
    Returns:
        (cleaned_count, total_samples) 元组
    """
    try:
        with open(fragment_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理不同的数据格式
        samples = []
        if isinstance(data, dict):
            samples = data.get("samples", [])
        elif isinstance(data, list):
            samples = data
        else:
            logger.warning(f"Unexpected data format in {fragment_file}")
            return (0, 0)
        
        cleaned_count = 0
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            
            metrics = sample.get("metrics", {})
            for metric_name, metric_result in metrics.items():
                if not isinstance(metric_result, dict):
                    continue
                
                # 检查是否是失败的指标：success=False 且 score=0.0
                success = metric_result.get("success")
                score = metric_result.get("score")
                
                # 处理不同的 success 值类型
                if isinstance(success, str):
                    is_failed = success.lower() in ('false', '0', 'no')
                else:
                    is_failed = success is False
                
                # 如果 success=False 且 score=0.0，改为 score=None
                if is_failed and score == 0.0:
                    metric_result["score"] = None
                    cleaned_count += 1
                    logger.debug(f"Cleaned {metric_name} for {sample.get('sample_id', 'unknown')}/{sample.get('model', 'unknown')}")
        
        if cleaned_count > 0:
            # 保存清理后的数据
            with open(fragment_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cleaned {cleaned_count} failed metrics in {fragment_file.name}")
        
        return (cleaned_count, len(samples))
    
    except Exception as e:
        logger.error(f"Error processing {fragment_file}: {e}")
        return (0, 0)


def cleanup_all_fragments(fragments_dir: Path) -> Dict[str, Any]:
    """
    清理所有分片文件
    
    Returns:
        统计信息字典
    """
    if not fragments_dir.exists():
        logger.error(f"Fragments directory not found: {fragments_dir}")
        return {}
    
    fragment_files = list(fragments_dir.glob("*_results.json"))
    logger.info(f"Found {len(fragment_files)} fragment files to process")
    
    total_cleaned = 0
    total_samples = 0
    file_stats = []
    
    for fragment_file in fragment_files:
        cleaned, samples = cleanup_fragment_file(fragment_file)
        total_cleaned += cleaned
        total_samples += samples
        if cleaned > 0:
            file_stats.append({
                "file": fragment_file.name,
                "cleaned": cleaned,
                "samples": samples
            })
    
    stats = {
        "total_files": len(fragment_files),
        "files_cleaned": len(file_stats),
        "total_metrics_cleaned": total_cleaned,
        "total_samples": total_samples,
        "file_details": file_stats
    }
    
    logger.info(f"Cleanup completed: {total_cleaned} failed metrics cleaned across {len(file_stats)} files")
    return stats


def main():
    """主函数"""
    import sys
    
    # 默认使用 task1_evaluation/fragments 目录
    if len(sys.argv) > 1:
        fragments_dir = Path(sys.argv[1])
    else:
        # 从脚本位置推断
        script_dir = Path(__file__).parent.parent.parent
        fragments_dir = script_dir / "data" / "task1_evaluation" / "fragments"
    
    if not fragments_dir.exists():
        logger.error(f"Fragments directory not found: {fragments_dir}")
        logger.info("Usage: python cleanup_failed_metrics.py [fragments_dir]")
        sys.exit(1)
    
    logger.info(f"Cleaning failed metrics in: {fragments_dir}")
    stats = cleanup_all_fragments(fragments_dir)
    
    # 打印统计信息
    print("\n" + "="*60)
    print("Cleanup Statistics:")
    print("="*60)
    print(f"Total fragment files: {stats['total_files']}")
    print(f"Files with cleaned metrics: {stats['files_cleaned']}")
    print(f"Total metrics cleaned: {stats['total_metrics_cleaned']}")
    print(f"Total samples processed: {stats['total_samples']}")
    print("="*60)
    
    if stats['file_details']:
        print("\nFiles with cleaned metrics:")
        for detail in stats['file_details']:
            print(f"  - {detail['file']}: {detail['cleaned']} metrics cleaned ({detail['samples']} samples)")


if __name__ == "__main__":
    main()

