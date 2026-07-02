#!/usr/bin/env python3
"""
Generate task2_benchmark reports:
1. single_question_files_report.json - Report of all question_set.json files with only one question
2. task2_progress.json - Initial progress file for model editing
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def generate_single_question_report(benchmark_dir: Path) -> Dict[str, Any]:
    """
    生成单个问题文件报告
    
    Args:
        benchmark_dir: task2_benchmark目录
        
    Returns:
        报告字典
    """
    logger.info("=" * 80)
    logger.info("Generating Single Question Files Report")
    logger.info("=" * 80)
    
    single_question_files = []
    total_files = 0
    
    # 扫描所有领域
    domain_dirs = sorted([d for d in benchmark_dir.glob('domain_*') if d.is_dir()])
    logger.info(f"Found {len(domain_dirs)} domains")
    
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        logger.debug(f"Processing domain: {domain}")
        
        # 扫描所有样本
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        
        for sample_dir in sample_dirs:
            instructions_dir = sample_dir / "instructions"
            if not instructions_dir.exists():
                continue
            
            # 扫描所有指令目录
            instruction_dirs = sorted([d for d in instructions_dir.glob('inst_*') if d.is_dir()])
            
            for inst_dir in instruction_dirs:
                question_set_path = inst_dir / "question_set.json"
                
                if not question_set_path.exists():
                    continue
                
                total_files += 1
                
                try:
                    with open(question_set_path, 'r', encoding='utf-8') as f:
                        question_data = json.load(f)
                    
                    # 检查问题数量
                    questions = question_data.get('decomposed_questions', [])
                    if len(questions) == 1:
                        # 获取相对路径
                        rel_path = question_set_path.relative_to(benchmark_dir)
                        
                        # 读取指令文本
                        instruction_text = question_data.get('instruction', '')
                        if not instruction_text:
                            instruction_txt_path = inst_dir / "instruction.txt"
                            if instruction_txt_path.exists():
                                with open(instruction_txt_path, 'r', encoding='utf-8') as f:
                                    instruction_text = f.read().strip()
                        
                        single_question_files.append({
                            "path": str(rel_path),
                            "instruction_id": question_data.get('instruction_id', inst_dir.name),
                            "instruction": instruction_text,
                            "question": questions[0] if questions else ""
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to process {question_set_path}: {e}")
    
    # 生成报告
    report = {
        "total_single_question_files": len(single_question_files),
        "total_files": total_files,
        "ratio": (len(single_question_files) / total_files * 100) if total_files > 0 else 0.0,
        "files": single_question_files
    }
    
    logger.info(f"Total question_set.json files: {total_files}")
    logger.info(f"Single question files: {len(single_question_files)}")
    logger.info(f"Ratio: {report['ratio']:.2f}%")
    
    return report


def generate_initial_progress_file(benchmark_dir: Path) -> Dict[str, Any]:
    """
    生成初始进度文件
    
    Args:
        benchmark_dir: task2_benchmark目录
        
    Returns:
        进度字典
    """
    logger.info("=" * 80)
    logger.info("Generating Initial Progress File")
    logger.info("=" * 80)
    
    domain_stats = {}
    total_instructions = 0
    
    # 扫描所有领域
    domain_dirs = sorted([d for d in benchmark_dir.glob('domain_*') if d.is_dir()])
    
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        domain_instructions = 0
        
        # 扫描所有样本
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        
        for sample_dir in sample_dirs:
            instructions_dir = sample_dir / "instructions"
            if instructions_dir.exists():
                instruction_dirs = sorted([d for d in instructions_dir.glob('inst_*') if d.is_dir()])
                domain_instructions += len(instruction_dirs)
        
        if domain_instructions > 0:
            domain_stats[domain] = {
                "processed": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0
            }
            total_instructions += domain_instructions
    
    progress = {
        "timestamp": datetime.now().isoformat(),
        "models": [],
        "total_processed": 0,
        "total_success": 0,
        "total_failed": 0,
        "success_rate": 0.0,
        "domains": domain_stats
    }
    
    logger.info(f"Total instructions: {total_instructions}")
    logger.info(f"Domains: {len(domain_stats)}")
    
    return progress


def main():
    parser = argparse.ArgumentParser(
        description="Generate task2_benchmark reports"
    )
    
    parser.add_argument(
        '--benchmark',
        type=Path,
        default=Path(__file__).parent.parent.parent / 'data' / 'task2_benchmark1',
        help='Benchmark directory (default: data/task2_benchmark1)'
    )
    parser.add_argument(
        '--single-question-only',
        action='store_true',
        help='Only generate single_question_files_report.json'
    )
    parser.add_argument(
        '--progress-only',
        action='store_true',
        help='Only generate task2_progress.json'
    )
    
    args = parser.parse_args()
    
    # Validate
    if not args.benchmark.exists():
        logger.error(f"Benchmark directory not found: {args.benchmark}")
        return 1
    
    try:
        # 生成单个问题文件报告
        if not args.progress_only:
            logger.info("\n" + "=" * 80)
            single_question_report = generate_single_question_report(args.benchmark)
            
            report_path = args.benchmark / "single_question_files_report.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(single_question_report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"\n✓ Single question report saved to: {report_path}")
        
        # 生成初始进度文件
        if not args.single_question_only:
            logger.info("\n" + "=" * 80)
            progress = generate_initial_progress_file(args.benchmark)
            
            progress_path = args.benchmark / "task2_progress.json"
            with open(progress_path, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
            
            logger.info(f"\n✓ Progress file saved to: {progress_path}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ All reports generated successfully")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

