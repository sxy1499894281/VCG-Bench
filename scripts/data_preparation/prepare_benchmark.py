#!/usr/bin/env python3
"""
Prepare Task 2 benchmark data from Task 1 filtered Gemini results
从task1_benchmark提取筛选后的Gemini结果到task2_benchmark
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Setup logging
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'prepare_benchmark.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def extract_approved_samples(source_dir: Path, target_dir: Path):
    """
    提取筛选后的Gemini结果
    
    Args:
        source_dir: task1_benchmark目录
        target_dir: task2_benchmark目录
    """
    logger.info("=" * 80)
    logger.info("Prepare Task 2 Benchmark Data")
    logger.info("=" * 80)
    logger.info(f"Source: {source_dir}")
    logger.info(f"Target: {target_dir}")
    
    approved_samples = []
    
    # 扫描所有领域
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        domain = domain_dir.name
        logger.info(f"\nProcessing domain: {domain}")
        
        # 创建领域输出目录
        domain_output_dir = target_dir / domain
        domain_output_dir.mkdir(parents=True, exist_ok=True)
        
        domain_approved = 0
        
        # 扫描所有样本
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            # 查找Gemini模型目录（查找包含"gemini"的模型目录）
            gemini_dir = None
            status_path = None
            
            # 优先查找 gemini-3-pro-preview
            desc_model_name = "gemini-3-pro-preview"
            candidate_dir = sample_dir / f"model_{desc_model_name}"
            if candidate_dir.exists():
                candidate_status = candidate_dir / "screening_status.json"
                if candidate_status.exists():
                    gemini_dir = candidate_dir
                    status_path = candidate_status
            
            # 如果没找到，查找所有包含"gemini"的模型目录
            if gemini_dir is None:
                for model_dir in sample_dir.glob('model_*'):
                    if 'gemini' in model_dir.name.lower():
                        candidate_status = model_dir / "screening_status.json"
                        if candidate_status.exists():
                            gemini_dir = model_dir
                            status_path = candidate_status
                            break
            
            # 检查筛选状态
            if gemini_dir is None or status_path is None or not status_path.exists():
                logger.debug(f"Sample {sample_dir.name} has no screening status, skipping")
                continue
            
            with open(status_path, 'r', encoding='utf-8') as f:
                status = json.load(f)
                if status.get('status') != 'approved':
                    logger.debug(f"Sample {sample_dir.name} not approved (status: {status.get('status')}), skipping")
                    continue
            
            # 提取样本
            sample_id = sample_dir.name
            target_sample_dir = domain_output_dir / sample_id
            target_sample_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            files_to_copy = [
                ("original.png", sample_dir / "original.png"),
                ("llm_description.txt", gemini_dir / "llm_description.txt"),
                ("diagram.xml", gemini_dir / "diagram.xml"),
                ("rendered.png", gemini_dir / "rendered.png"),
                ("metadata.json", sample_dir / "metadata.json")
            ]
            
            copied = 0
            for target_name, source_path in files_to_copy:
                if source_path.exists():
                    target_path = target_sample_dir / target_name
                    shutil.copy2(source_path, target_path)
                    logger.debug(f"Copied {target_name} to {target_sample_dir}")
                    copied += 1
                else:
                    logger.warning(f"Source file not found: {source_path}")
            
            if copied > 0:
                approved_samples.append({
                    "domain": domain,
                    "sample_id": sample_id,
                    "path": str(target_sample_dir)
                })
                domain_approved += 1
                logger.info(f"✓ Extracted sample {sample_id} ({copied} files)")
            else:
                logger.warning(f"No files copied for sample {sample_id}")
        
        logger.info(f"Domain {domain}: {domain_approved} approved samples extracted")
    
    # 生成统计信息
    logger.info("\n" + "=" * 80)
    logger.info("Extraction Summary")
    logger.info("=" * 80)
    logger.info(f"Total approved samples extracted: {len(approved_samples)}")
    
    # 按领域统计
    domain_stats = {}
    for sample in approved_samples:
        domain = sample['domain']
        domain_stats[domain] = domain_stats.get(domain, 0) + 1
    
    for domain, count in domain_stats.items():
        logger.info(f"  {domain}: {count} samples")
    
    # 保存索引
    index_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "task": "task2",
        "source": str(source_dir),
        "total_samples": len(approved_samples),
        "statistics": {
            "by_domain": domain_stats
        },
        "samples": approved_samples
    }
    
    index_path = target_dir / "dataset.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    logger.info(f"\nIndex saved to {index_path}")
    
    return len(approved_samples)


def main():
    parser = argparse.ArgumentParser(
        description="Prepare Task 2 benchmark data from Task 1 filtered Gemini results"
    )
    
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (task1_benchmark)')
    parser.add_argument('--target', type=Path, required=True,
                        help='Target directory (task2_benchmark)')
    
    args = parser.parse_args()
    
    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1
    
    # 创建目标目录
    args.target.mkdir(parents=True, exist_ok=True)
    
    # 提取数据
    try:
        count = extract_approved_samples(args.source, args.target)
        logger.info(f"\n✓ Successfully extracted {count} samples")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
