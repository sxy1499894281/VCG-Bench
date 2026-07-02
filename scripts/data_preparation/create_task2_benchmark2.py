#!/usr/bin/env python3
"""
Create a subset of task2_benchmark for faster evaluation.
从task2_benchmark_origin抽取一个新的benchmark2：
- 保留第一个领域的所有162个样本
- 从其他领域随机抽取300个样本
- 总共462个样本
"""

import argparse
import json
import logging
import random
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def copy_sample_directory(source_sample_dir: Path, target_sample_dir: Path):
    """复制整个样本目录"""
    target_sample_dir.parent.mkdir(parents=True, exist_ok=True)
    
    # 使用shutil.copytree复制整个目录
    if target_sample_dir.exists():
        shutil.rmtree(target_sample_dir)
    
    shutil.copytree(source_sample_dir, target_sample_dir)
    logger.debug(f"Copied {source_sample_dir.name} to {target_sample_dir}")


def create_benchmark_subset(
    source_dir: Path,
    target_dir: Path,
    target_samples_from_other_domains: int = 300,
    seed: int = 42
):
    """
    创建benchmark子集（包含第一个领域 + 其他领域随机抽取）
    
    Args:
        source_dir: 源目录 (task2_benchmark_origin)
        target_dir: 目标目录 (task2_benchmark2)
        target_samples_from_other_domains: 从其他领域抽取的样本数（默认300）
        seed: 随机种子
    """
    logger.info("=" * 80)
    logger.info("Create Task 2 Benchmark Subset")
    logger.info("=" * 80)
    logger.info(f"Source: {source_dir}")
    logger.info(f"Target: {target_dir}")
    logger.info(f"Target samples from other domains: {target_samples_from_other_domains}")
    
    # 设置随机种子
    random.seed(seed)
    
    # 获取所有领域目录（按字母顺序排序）
    domain_dirs = sorted([d for d in source_dir.glob('domain_*') if d.is_dir()])
    
    if not domain_dirs:
        logger.error("No domain directories found in source directory")
        return None
    
    logger.info(f"\nFound {len(domain_dirs)} domains:")
    for domain_dir in domain_dirs:
        sample_count = len(list(domain_dir.glob('sample_*')))
        logger.info(f"  {domain_dir.name}: {sample_count} samples")
    
    # 第一个领域（保留所有样本）
    first_domain = domain_dirs[0]
    first_domain_name = first_domain.name
    first_domain_samples = sorted([d for d in first_domain.glob('sample_*') if d.is_dir()])
    first_domain_count = len(first_domain_samples)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"First domain: {first_domain_name}")
    logger.info(f"Keeping all {first_domain_count} samples from first domain")
    
    # 收集其他领域的所有样本
    other_domains_samples: Dict[str, List[Path]] = {}
    total_other_samples = 0
    
    for domain_dir in domain_dirs[1:]:
        domain_name = domain_dir.name
        samples = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        if samples:
            other_domains_samples[domain_name] = samples
            total_other_samples += len(samples)
            logger.debug(f"  {domain_name}: {len(samples)} samples available")
    
    logger.info(f"\nTotal samples available in other domains: {total_other_samples}")
    logger.info(f"Samples needed from other domains: {target_samples_from_other_domains}")
    
    if target_samples_from_other_domains > total_other_samples:
        logger.warning(f"Not enough samples in other domains. Will use all {total_other_samples} samples")
        selected_samples = other_domains_samples
    else:
        # 按比例从每个领域抽取
        # 先计算每个领域应该抽取的数量（按比例）
        domain_allocations = {}
        remaining_to_allocate = target_samples_from_other_domains
        
        # 按领域大小分配
        sorted_domains = sorted(
            other_domains_samples.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        for domain_name, samples in sorted_domains:
            if remaining_to_allocate <= 0:
                break
            
            # 按比例分配，但至少每个领域至少抽取1个（如果有的话）
            proportion = len(samples) / total_other_samples
            allocated = max(1, int(proportion * target_samples_from_other_domains))
            allocated = min(allocated, len(samples), remaining_to_allocate)
            
            domain_allocations[domain_name] = allocated
            remaining_to_allocate -= allocated
        
        # 如果还有剩余，分配给最大的领域
        if remaining_to_allocate > 0:
            for domain_name, samples in sorted_domains:
                if remaining_to_allocate <= 0:
                    break
                if domain_name in domain_allocations:
                    can_add = min(remaining_to_allocate, len(samples) - domain_allocations[domain_name])
                    domain_allocations[domain_name] += can_add
                    remaining_to_allocate -= can_add
        
        # 从每个领域随机抽取
        selected_samples: Dict[str, List[Path]] = {}
        for domain_name, samples in other_domains_samples.items():
            if domain_name in domain_allocations:
                num_to_select = domain_allocations[domain_name]
                selected = random.sample(samples, num_to_select)
                selected_samples[domain_name] = selected
                logger.info(f"  {domain_name}: selected {num_to_select}/{len(samples)} samples")
    
    # 创建目标目录
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制第一个领域的所有样本
    logger.info(f"\n{'='*80}")
    logger.info("Copying samples...")
    logger.info(f"{'='*80}")
    
    first_domain_target = target_dir / first_domain_name
    copied_count = 0
    
    for sample_dir in first_domain_samples:
        target_sample_dir = first_domain_target / sample_dir.name
        copy_sample_directory(sample_dir, target_sample_dir)
        copied_count += 1
        if copied_count % 20 == 0:
            logger.info(f"  Copied {copied_count}/{first_domain_count} samples from first domain...")
    
    logger.info(f"✓ Copied {copied_count} samples from first domain")
    
    # 复制其他领域选中的样本
    other_copied_count = 0
    for domain_name, samples in selected_samples.items():
        domain_target = target_dir / domain_name
        for sample_dir in samples:
            target_sample_dir = domain_target / sample_dir.name
            copy_sample_directory(sample_dir, target_sample_dir)
            other_copied_count += 1
            if other_copied_count % 50 == 0:
                logger.info(f"  Copied {other_copied_count} samples from other domains...")
    
    logger.info(f"✓ Copied {other_copied_count} samples from other domains")
    
    total_copied = copied_count + other_copied_count
    logger.info(f"✓ Total samples copied: {total_copied}")
    
    # 生成统计信息
    domain_stats = {}
    domain_stats[first_domain_name] = first_domain_count
    for domain_name, samples in selected_samples.items():
        domain_stats[domain_name] = len(samples)
    
    # 生成dataset.json（简化版，只包含基本信息）
    dataset_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "task": "task2",
        "source": str(source_dir.name),
        "subset_info": {
            "target_samples_from_other_domains": target_samples_from_other_domains,
            "first_domain": first_domain_name,
            "first_domain_samples": first_domain_count,
            "other_domains_samples": other_copied_count,
            "random_seed": seed
        },
        "total_samples": total_copied,
        "statistics": {
            "by_domain": domain_stats
        }
    }
    
    dataset_path = target_dir / "dataset.json"
    with open(dataset_path, 'w', encoding='utf-8') as f:
        json.dump(dataset_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Dataset index saved to {dataset_path}")
    
    # 打印最终统计
    logger.info("\n" + "=" * 80)
    logger.info("Final Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples: {total_copied}")
    logger.info(f"First domain ({first_domain_name}): {first_domain_count} samples")
    logger.info(f"Other domains: {other_copied_count} samples")
    logger.info(f"\nDomain breakdown:")
    for domain_name, count in sorted(domain_stats.items()):
        logger.info(f"  {domain_name}: {count} samples")
    
    return {
        "total_samples": total_copied,
        "first_domain": first_domain_name,
        "first_domain_count": first_domain_count,
        "other_domains_count": other_copied_count,
        "domain_stats": domain_stats
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create a subset of task2_benchmark (first domain + 300 from others)"
    )
    
    parser.add_argument(
        '--source',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'data' / 'task2_benchmark_origin',
        help='Source directory (task2_benchmark_origin)'
    )
    parser.add_argument(
        '--target',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'data' / 'task2_benchmark2',
        help='Target directory (task2_benchmark2)'
    )
    parser.add_argument(
        '--target-samples',
        type=int,
        default=300,
        help='Target number of samples from other domains (default: 300)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for sampling (default: 42)'
    )
    
    args = parser.parse_args()
    
    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1
    
    # 创建目标目录
    args.target.mkdir(parents=True, exist_ok=True)
    
    # 创建子集
    try:
        result = create_benchmark_subset(
            args.source,
            args.target,
            args.target_samples,
            args.seed
        )
        if result:
            logger.info(f"\n✓ Successfully created benchmark subset with {result['total_samples']} samples")
            return 0
        else:
            logger.error("Failed to create benchmark subset")
            return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

