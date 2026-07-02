#!/usr/bin/env python3
"""
Evaluation entry point.

Run from the repository root, for example:
    python eval/run_evaluation.py task1 --benchmark data/task1_benchmark --output data/task1_evaluation
"""

import argparse
import logging
import sys
from pathlib import Path

# Add repository root to sys.path so this file works when executed as a script.
vcgbench_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(vcgbench_root))

# Load .env before importing modules that read provider settings.
from dotenv import load_dotenv
env_loaded = False

env_path = vcgbench_root / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)
    env_loaded = True

if not env_loaded:
    env_path = vcgbench_root.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=True)
        env_loaded = True

from eval.task1.evaluator import Task1Evaluator
from eval.task2.evaluator import Task2Evaluator
from src.llm.client import LLMClient
from src.renderer.drawio_renderer import DrawioRenderer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import os


def log_env_status():
    """Log API environment status after CLI arguments are parsed."""
    if os.getenv('CUSTOM_API_KEY') and os.getenv('CUSTOM_BASE_URL'):
        logger.info("Environment variables loaded successfully")
    else:
        logger.warning("CUSTOM_API_KEY or CUSTOM_BASE_URL not found in environment")


def run_task1(
    benchmark_dir: Path,
    output_dir: Path,
    models: list = None,
    enabled_metrics: list = None,
    domain_filter: list = None
):
    """运行任务一评估"""
    logger.info("=" * 80)
    logger.info("Task 1: Image to XML Generation Evaluation")
    logger.info("=" * 80)
    
    # 初始化评估器
    llm_client = LLMClient()
    renderer = DrawioRenderer()
    evaluator = Task1Evaluator(
        llm_client=llm_client,
        renderer=renderer,
        enabled_metrics=enabled_metrics
    )
    
    # 运行评估
    evaluator.evaluate_all(
        benchmark_dir=benchmark_dir,
        output_dir=output_dir,
        models=models,
        domain_filter=domain_filter
    )
    
    logger.info("Task 1 evaluation completed!")


def run_task2(
    benchmark_dir: Path,
    output_dir: Path,
    models: list = None,
    enabled_metrics: list = None,
    domain_filter: list = None
):
    """运行任务二评估"""
    logger.info("=" * 80)
    logger.info("Task 2: Instruction-driven XML Editing Evaluation")
    logger.info("=" * 80)
    
    # 初始化评估器
    llm_client = LLMClient()
    renderer = DrawioRenderer()
    evaluator = Task2Evaluator(
        llm_client=llm_client,
        renderer=renderer,
        enabled_metrics=enabled_metrics
    )
    
    # 运行评估
    evaluator.evaluate_all(
        benchmark_dir=benchmark_dir,
        output_dir=output_dir,
        models=models,
        domain_filter=domain_filter
    )
    
    logger.info("Task 2 evaluation completed!")


def main():
    parser = argparse.ArgumentParser(
        description="VCG-Bench evaluation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (run from the VCG-Bench repository root):

1. 评估任务一（所有指标，所有模型）：
   cd VCG-Bench
   python eval/run_evaluation.py task1 \\
       --benchmark data/task1_benchmark \\
       --output data/task1_evaluation

2. 评估任务二（所有指标，所有模型）：
   cd VCG-Bench
   python eval/run_evaluation.py task2 \\
       --benchmark data/task2_benchmark \\
       --output data/task2_evaluation

3. 只评估特定模型：
   cd VCG-Bench
   python eval/run_evaluation.py task1 \\
       --benchmark data/task1_benchmark \\
       --output data/task1_evaluation \\
       --models gemini claude

4. 只启用特定指标（节省时间）：
   cd VCG-Bench
   python eval/run_evaluation.py task1 \\
       --benchmark data/task1_benchmark \\
       --output data/task1_evaluation \\
       --metrics execution_success_rate xml_token_count

5. 禁用特定指标：
   cd VCG-Bench
   python eval/run_evaluation.py task1 \\
       --benchmark data/task1_benchmark \\
       --output data/task1_evaluation \\
       --disable-metrics structural_fidelity  # 跳过耗时的结构保真度
        """
    )
    
    parser.add_argument(
        'task',
        choices=['task1', 'task2'],
        help='要评估的任务（task1: 图片到XML生成, task2: 指令驱动的XML编辑）'
    )
    
    parser.add_argument(
        '--benchmark',
        type=Path,
        required=True,
        help='Benchmark数据目录路径（如 data/task1_benchmark，相对于 VCG-Bench 根目录）'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='评估结果输出目录（如 data/task1_evaluation，相对于 VCG-Bench 根目录）'
    )
    
    parser.add_argument(
        '--models',
        nargs='+',
        default=None,
        help='要评估的模型列表（如 gemini claude），默认评估所有模型'
    )
    
    parser.add_argument(
        '--metrics',
        nargs='+',
        default=None,
        help='要启用的指标列表（默认启用所有指标）'
    )
    
    parser.add_argument(
        '--disable-metrics',
        nargs='+',
        default=None,
        help='要禁用的指标列表（用于跳过耗时的指标）'
    )
    
    parser.add_argument(
        '--domain',
        nargs='+',
        default=None,
        help='要评估的领域列表（如 domain_academic_domain_architecture domain_business_domain_product），默认评估所有领域。支持并行评估：每个领域运行独立进程。'
    )
    
    args = parser.parse_args()
    log_env_status()
    
    # 处理指标启用/禁用
    enabled_metrics = None
    if args.metrics:
        enabled_metrics = args.metrics
    elif args.disable_metrics:
        # 获取所有指标，然后移除禁用的
        if args.task == 'task1':
            all_metrics = [
                'execution_success_rate',
                'xml_token_count',
                'style_consistency_score',
                'codevqa',
                'siglip_score'
            ]
        else:
            all_metrics = [
                'modified_xml_execution_success_rate',
                'modified_xml_token_count',
                'modification_json_token_count',
                'style_consistency_score_task2',
                'xdrfr',
                'xml_edit_distance'
            ]
        enabled_metrics = [m for m in all_metrics if m not in args.disable_metrics]
    
    # Resolve relative paths against the repository root.
    vcgbench_root = Path(__file__).resolve().parent.parent
    original_cwd = Path.cwd()
    
    # 如果benchmark路径是相对路径，尝试相对于 VCG-Bench 根目录解析
    benchmark_path = Path(args.benchmark)
    if not benchmark_path.is_absolute():
        benchmark_path_vcgbench = vcgbench_root / args.benchmark
        if benchmark_path_vcgbench.exists():
            args.benchmark = benchmark_path_vcgbench
            logger.info(f"Resolved benchmark path relative to VCG-Bench root: {args.benchmark}")
        # 如果还是不存在，尝试相对于当前工作目录（保持原有行为）
        elif not args.benchmark.exists():
            logger.warning(
                f"Benchmark directory not found at: {args.benchmark}\n"
                f"  Tried relative to VCG-Bench root: {benchmark_path_vcgbench}\n"
                f"  Current working directory: {original_cwd}\n"
                f"  VCG-Bench root: {vcgbench_root}"
            )
    
    # 检查benchmark目录
    if not args.benchmark.exists():
        logger.error(f"Benchmark directory not found: {args.benchmark}")
        return 1
    
    # 对于输出目录也做同样处理
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path_vcgbench = vcgbench_root / args.output
        args.output = output_path_vcgbench
        logger.info(f"Resolved output path relative to VCG-Bench root: {args.output}")
    
    # 运行评估
    try:
        if args.task == 'task1':
            run_task1(
                benchmark_dir=args.benchmark,
                output_dir=args.output,
                models=args.models,
                enabled_metrics=enabled_metrics,
                domain_filter=args.domain
            )
        else:
            run_task2(
                benchmark_dir=args.benchmark,
                output_dir=args.output,
                models=args.models,
                enabled_metrics=enabled_metrics,
                domain_filter=args.domain
            )
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
