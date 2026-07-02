#!/usr/bin/env python3
"""
Generate index files for Task 1 and Task 2
生成任务1和任务2的索引文件
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent.parent / 'logs' / 'generate_index.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def generate_task1_index(source_dir: Path, output_path: Path):
    """
    生成任务1索引
    
    Args:
        source_dir: task1_benchmark目录
        output_path: 输出索引文件路径
    """
    logger.info("=" * 80)
    logger.info("Generating Task 1 Index")
    logger.info("=" * 80)
    
    samples = []
    domain_stats = {}
    model_stats = {}
    
    # 扫描所有领域
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        domain = domain_dir.name
        domain_samples = []
        
        # 扫描所有样本
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            sample_id = sample_dir.name
            sample_data = {
                "id": sample_id,
                "domain": domain,
                "path": f"{domain}/{sample_id}",
                "metadata_path": f"{domain}/{sample_id}/metadata.json",
                "models": {}
            }
            
            # 扫描所有模型
            for model_dir in sample_dir.glob('model_*'):
                if not model_dir.is_dir():
                    continue
                
                model_name = model_dir.name.replace('model_', '')
                
                # 检查状态
                xml_path = model_dir / "diagram.xml"
                error_path = model_dir / "error.json"
                
                if xml_path.exists():
                    sample_data["models"][model_name] = {
                        "status": "success",
                        "has_xml": True,
                        "has_rendered": (model_dir / "rendered.png").exists()
                    }
                elif error_path.exists():
                    with open(error_path, 'r', encoding='utf-8') as f:
                        error_info = json.load(f)
                    sample_data["models"][model_name] = {
                        "status": "failed",
                        "error_path": f"{domain}/{sample_id}/{model_dir.name}/error.json",
                        "error_type": error_info.get('error_type'),
                        "error_message": error_info.get('error_message', '')[:100]  # 只显示前100字符
                    }
                else:
                    sample_data["models"][model_name] = {
                        "status": "pending"
                    }
                
                # 统计
                if model_name not in model_stats:
                    model_stats[model_name] = {"success": 0, "failed": 0, "pending": 0}
                
                status = sample_data["models"][model_name]["status"]
                if status == "success":
                    model_stats[model_name]["success"] += 1
                elif status == "failed":
                    model_stats[model_name]["failed"] += 1
                else:
                    model_stats[model_name]["pending"] += 1
            
            samples.append(sample_data)
            domain_samples.append(sample_data)
        
        domain_stats[domain] = len(domain_samples)
    
    # 生成索引
    index_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "task": "task1",
        "total_samples": len(samples),
        "statistics": {
            "by_domain": domain_stats,
            "by_model_status": model_stats
        },
        "samples": samples
    }
    
    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Index saved to {output_path}")
    logger.info(f"Total samples: {len(samples)}")
    logger.info(f"Domains: {list(domain_stats.keys())}")
    logger.info(f"Models: {list(model_stats.keys())}")


def generate_task2_index(source_dir: Path, output_path: Path):
    """
    生成任务2索引（待完整实现）
    
    Args:
        source_dir: task2_benchmark目录
        output_path: 输出索引文件路径
    """
    logger.info("=" * 80)
    logger.info("Generating Task 2 Index")
    logger.info("=" * 80)
    logger.warning("Task 2 index generation not yet fully implemented")
    
    # 占位实现
    index_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "task": "task2",
        "total_samples": 0,
        "statistics": {},
        "samples": []
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Placeholder index saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate index files for Task 1 and Task 2"
    )
    
    subparsers = parser.add_subparsers(dest='task', help='Task to generate index for')
    
    # Task 1
    task1_parser = subparsers.add_parser('task1', help='Generate Task 1 index')
    task1_parser.add_argument('--source', type=Path, required=True,
                              help='Source directory (task1_benchmark)')
    task1_parser.add_argument('--output', type=Path, required=True,
                              help='Output index file path')
    
    # Task 2
    task2_parser = subparsers.add_parser('task2', help='Generate Task 2 index')
    task2_parser.add_argument('--source', type=Path, required=True,
                              help='Source directory (task2_benchmark)')
    task2_parser.add_argument('--output', type=Path, required=True,
                              help='Output index file path')
    
    args = parser.parse_args()
    
    if not args.task:
        parser.print_help()
        return 1
    
    try:
        if args.task == 'task1':
            if not args.source.exists():
                logger.error(f"Source directory not found: {args.source}")
                return 1
            generate_task1_index(args.source, args.output)
            
        elif args.task == 'task2':
            if not args.source.exists():
                logger.error(f"Source directory not found: {args.source}")
                return 1
            generate_task2_index(args.source, args.output)
        
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

