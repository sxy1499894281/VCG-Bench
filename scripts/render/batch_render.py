#!/usr/bin/env python3
"""
批量渲染脚本 - 用于本地机器渲染HPC服务器生成的XML文件
将data/task1_benchmark和data/task2_benchmark中所有的XML文件渲染为PNG
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.renderer.drawio_renderer import DrawioRenderer
from src.core.models import DiagramXML

# Setup logging
log_dir = project_root / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'batch_render.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def render_single_file(args: Tuple[Path, Path, str]) -> Tuple[Path, bool, str]:
    """
    渲染单个XML文件

    Args:
        args: (xml_path, output_path, drawio_path) 元组

    Returns:
        (xml_path, success, error_message)
    """
    xml_path, output_path, drawio_path = args

    try:
        # 确保路径是 Path 对象（多进程序列化可能导致类型丢失）
        xml_path = Path(xml_path)
        output_path = Path(output_path)
        drawio_path = Path(drawio_path) if drawio_path else None
        
        # 读取 XML 文件内容
        xml_content = xml_path.read_text(encoding='utf-8')
        
        # 创建 DiagramXML 对象
        diagram = DiagramXML(
            xml_content=xml_content,
            diagram_type="unknown",  # 批量渲染不需要验证类型
            is_valid=True  # 假设文件是有效的，让 draw.io 决定
        )
        
        # 初始化渲染器
        renderer = DrawioRenderer(drawio_path=drawio_path, skip_render=False)

        # 渲染
        success = renderer.render(diagram, output_path)

        if success:
            return (xml_path, True, "")
        else:
            return (xml_path, False, "Rendering failed")

    except Exception as e:
        logger.error(f"Error rendering {xml_path}: {e}")
        return (xml_path, False, str(e))


def find_task1_xml_files(benchmark_dir: Path) -> List[Tuple[Path, Path]]:
    """
    查找Task 1中所有需要渲染的XML文件

    Returns:
        List of (xml_path, output_png_path)
    """
    files = []

    # Task 1: domain_*/sample_*/model_*/diagram.xml -> model_*/rendered.png
    for domain_dir in sorted(benchmark_dir.glob('domain_*')):
        if not domain_dir.is_dir():
            continue

        for sample_dir in sorted(domain_dir.glob('sample_*')):
            if not sample_dir.is_dir():
                continue

            for model_dir in sorted(sample_dir.glob('model_*')):
                if not model_dir.is_dir():
                    continue

                xml_path = model_dir / 'diagram.xml'
                output_path = model_dir / 'rendered.png'

                if xml_path.exists():
                    files.append((xml_path, output_path))

    return files


def find_task2_xml_files(benchmark_dir: Path) -> List[Tuple[Path, Path]]:
    """
    查找Task 2中所有需要渲染的XML文件

    Returns:
        List of (xml_path, output_png_path)
    """
    files = []

    # Task 2: domain_*/sample_*/instructions/inst_*/model_*/modified.xml -> model_*/modified.png
    for domain_dir in sorted(benchmark_dir.glob('domain_*')):
        if not domain_dir.is_dir():
            continue

        for sample_dir in sorted(domain_dir.glob('sample_*')):
            if not sample_dir.is_dir():
                continue

            instructions_dir = sample_dir / 'instructions'
            if not instructions_dir.exists():
                continue

            for inst_dir in sorted(instructions_dir.glob('inst_*')):
                if not inst_dir.is_dir():
                    continue

                for model_dir in sorted(inst_dir.glob('model_*')):
                    if not model_dir.is_dir():
                        continue

                    xml_path = model_dir / 'modified.xml'
                    output_path = model_dir / 'modified.png'

                    if xml_path.exists():
                        files.append((xml_path, output_path))

    return files


def render_task1(
    benchmark_dir: Path,
    drawio_path: str = '/Applications/draw.io.app/Contents/MacOS/draw.io',
    num_workers: int = None,
    skip_existing: bool = True
) -> dict:
    """
    批量渲染Task 1中的所有XML文件

    Args:
        benchmark_dir: task1_benchmark目录
        drawio_path: draw.io可执行文件路径
        num_workers: 并发进程数（None表示使用CPU核心数）
        skip_existing: 是否跳过已存在的PNG文件

    Returns:
        渲染统计信息
    """
    logger.info("=" * 80)
    logger.info("Task 1 Batch Rendering")
    logger.info("=" * 80)
    logger.info(f"Benchmark directory: {benchmark_dir}")
    logger.info(f"Draw.io path: {drawio_path}")
    logger.info(f"Workers: {num_workers or cpu_count()}")
    logger.info(f"Skip existing: {skip_existing}")

    # 查找所有XML文件
    files = find_task1_xml_files(benchmark_dir)
    logger.info(f"Found {len(files)} XML files")

    if not files:
        logger.warning("No XML files found")
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

    # 过滤已存在的文件
    if skip_existing:
        files_to_render = [(xml, png) for xml, png in files if not png.exists()]
        skipped = len(files) - len(files_to_render)
        logger.info(f"Skipped {skipped} existing files, {len(files_to_render)} files to render")
    else:
        files_to_render = files
        skipped = 0

    if not files_to_render:
        logger.info("All files already rendered")
        return {
            "total": len(files),
            "success": len(files),
            "failed": 0,
            "skipped": skipped,
            "errors": []
        }

    # 准备参数
    render_args = [(xml, png, drawio_path) for xml, png in files_to_render]

    # 并行渲染
    start_time = time.time()
    results = []

    if num_workers == 1:
        # 单进程模式（用于调试）
        for args in render_args:
            result = render_single_file(args)
            results.append(result)
            logger.info(f"Rendered {result[0].relative_to(benchmark_dir)}: {'✓' if result[1] else '✗'}")
    else:
        # 多进程模式
        with Pool(processes=num_workers or cpu_count()) as pool:
            for i, result in enumerate(pool.imap_unordered(render_single_file, render_args), 1):
                results.append(result)
                logger.info(f"[{i}/{len(render_args)}] Rendered {result[0].relative_to(benchmark_dir)}: {'✓' if result[1] else '✗'}")

    elapsed_time = time.time() - start_time

    # 统计结果
    success_count = sum(1 for _, success, _ in results if success)
    failed_count = len(results) - success_count
    errors = [(str(path.relative_to(benchmark_dir)), error) for path, success, error in results if not success]

    stats = {
        "total": len(files),
        "success": success_count + skipped,
        "failed": failed_count,
        "skipped": skipped,
        "elapsed_time_seconds": elapsed_time,
        "errors": errors
    }

    # 输出统计
    logger.info("=" * 80)
    logger.info("Task 1 Rendering Summary")
    logger.info("=" * 80)
    logger.info(f"Total files: {stats['total']}")
    logger.info(f"Successfully rendered: {success_count}")
    logger.info(f"Skipped (already exist): {skipped}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Total success: {stats['success']}")
    logger.info(f"Elapsed time: {elapsed_time:.2f}s")
    logger.info(f"Average time per file: {elapsed_time/len(files_to_render):.2f}s" if files_to_render else "N/A")

    if errors:
        logger.error(f"\nFailed files ({len(errors)}):")
        for path, error in errors[:10]:  # 只显示前10个错误
            logger.error(f"  {path}: {error}")
        if len(errors) > 10:
            logger.error(f"  ... and {len(errors)-10} more")

    return stats


def render_task2(
    benchmark_dir: Path,
    drawio_path: str = '/Applications/draw.io.app/Contents/MacOS/draw.io',
    num_workers: int = None,
    skip_existing: bool = True
) -> dict:
    """
    批量渲染Task 2中的所有XML文件

    Args:
        benchmark_dir: task2_benchmark目录
        drawio_path: draw.io可执行文件路径
        num_workers: 并发进程数（None表示使用CPU核心数）
        skip_existing: 是否跳过已存在的PNG文件

    Returns:
        渲染统计信息
    """
    logger.info("=" * 80)
    logger.info("Task 2 Batch Rendering")
    logger.info("=" * 80)
    logger.info(f"Benchmark directory: {benchmark_dir}")
    logger.info(f"Draw.io path: {drawio_path}")
    logger.info(f"Workers: {num_workers or cpu_count()}")
    logger.info(f"Skip existing: {skip_existing}")

    # 查找所有XML文件
    files = find_task2_xml_files(benchmark_dir)
    logger.info(f"Found {len(files)} XML files")

    if not files:
        logger.warning("No XML files found")
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

    # 过滤已存在的文件
    if skip_existing:
        files_to_render = [(xml, png) for xml, png in files if not png.exists()]
        skipped = len(files) - len(files_to_render)
        logger.info(f"Skipped {skipped} existing files, {len(files_to_render)} files to render")
    else:
        files_to_render = files
        skipped = 0

    if not files_to_render:
        logger.info("All files already rendered")
        return {
            "total": len(files),
            "success": len(files),
            "failed": 0,
            "skipped": skipped,
            "errors": []
        }

    # 准备参数
    render_args = [(xml, png, drawio_path) for xml, png in files_to_render]

    # 并行渲染
    start_time = time.time()
    results = []

    if num_workers == 1:
        # 单进程模式（用于调试）
        for args in render_args:
            result = render_single_file(args)
            results.append(result)
            logger.info(f"Rendered {result[0].relative_to(benchmark_dir)}: {'✓' if result[1] else '✗'}")
    else:
        # 多进程模式
        with Pool(processes=num_workers or cpu_count()) as pool:
            for i, result in enumerate(pool.imap_unordered(render_single_file, render_args), 1):
                results.append(result)
                logger.info(f"[{i}/{len(render_args)}] Rendered {result[0].relative_to(benchmark_dir)}: {'✓' if result[1] else '✗'}")

    elapsed_time = time.time() - start_time

    # 统计结果
    success_count = sum(1 for _, success, _ in results if success)
    failed_count = len(results) - success_count
    errors = [(str(path.relative_to(benchmark_dir)), error) for path, success, error in results if not success]

    stats = {
        "total": len(files),
        "success": success_count + skipped,
        "failed": failed_count,
        "skipped": skipped,
        "elapsed_time_seconds": elapsed_time,
        "errors": errors
    }

    # 输出统计
    logger.info("=" * 80)
    logger.info("Task 2 Rendering Summary")
    logger.info("=" * 80)
    logger.info(f"Total files: {stats['total']}")
    logger.info(f"Successfully rendered: {success_count}")
    logger.info(f"Skipped (already exist): {skipped}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Total success: {stats['success']}")
    logger.info(f"Elapsed time: {elapsed_time:.2f}s")
    logger.info(f"Average time per file: {elapsed_time/len(files_to_render):.2f}s" if files_to_render else "N/A")

    if errors:
        logger.error(f"\nFailed files ({len(errors)}):")
        for path, error in errors[:10]:  # 只显示前10个错误
            logger.error(f"  {path}: {error}")
        if len(errors) > 10:
            logger.error(f"  ... and {len(errors)-10} more")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="批量渲染Task 1和Task 2中的XML文件为PNG图像"
    )

    parser.add_argument('task', choices=['task1', 'task2', 'all'],
                        help='要渲染的任务: task1, task2, or all')
    parser.add_argument('--task1-dir', type=Path,
                        default=project_root / 'data' / 'task1_benchmark',
                        help='Task 1 benchmark目录 (default: data/task1_benchmark)')
    parser.add_argument('--task2-dir', type=Path,
                        default=project_root / 'data' / 'task2_benchmark',
                        help='Task 2 benchmark目录 (default: data/task2_benchmark)')
    parser.add_argument('--drawio-path', type=str,
                        default='/Applications/draw.io.app/Contents/MacOS/draw.io',
                        help='draw.io可执行文件路径 (default: /Applications/draw.io.app/Contents/MacOS/draw.io)')
    parser.add_argument('--workers', type=int, default=None,
                        help='并发进程数 (default: CPU核心数)')
    parser.add_argument('--no-skip-existing', action='store_true',
                        help='不跳过已存在的PNG文件，重新渲染所有文件')
    parser.add_argument('--report', type=Path,
                        help='保存渲染报告的JSON文件路径')

    args = parser.parse_args()

    # 确保日志目录存在
    (project_root / 'logs').mkdir(parents=True, exist_ok=True)

    skip_existing = not args.no_skip_existing

    # 渲染报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "drawio_path": args.drawio_path,
        "workers": args.workers or cpu_count(),
        "skip_existing": skip_existing,
        "tasks": {}
    }

    try:
        if args.task in ['task1', 'all']:
            if not args.task1_dir.exists():
                logger.error(f"Task 1 benchmark directory not found: {args.task1_dir}")
            else:
                stats = render_task1(
                    benchmark_dir=args.task1_dir,
                    drawio_path=args.drawio_path,
                    num_workers=args.workers,
                    skip_existing=skip_existing
                )
                report['tasks']['task1'] = stats

        if args.task in ['task2', 'all']:
            if not args.task2_dir.exists():
                logger.error(f"Task 2 benchmark directory not found: {args.task2_dir}")
            else:
                stats = render_task2(
                    benchmark_dir=args.task2_dir,
                    drawio_path=args.drawio_path,
                    num_workers=args.workers,
                    skip_existing=skip_existing
                )
                report['tasks']['task2'] = stats

        # 保存报告
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with open(args.report, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"\nRendering report saved to: {args.report}")

        # 最终统计
        logger.info("\n" + "=" * 80)
        logger.info("Final Summary")
        logger.info("=" * 80)

        total_files = sum(task.get('total', 0) for task in report['tasks'].values())
        total_success = sum(task.get('success', 0) for task in report['tasks'].values())
        total_failed = sum(task.get('failed', 0) for task in report['tasks'].values())
        total_time = sum(task.get('elapsed_time_seconds', 0) for task in report['tasks'].values())

        logger.info(f"Total files: {total_files}")
        logger.info(f"Total success: {total_success}")
        logger.info(f"Total failed: {total_failed}")
        logger.info(f"Total time: {total_time:.2f}s")

        if total_failed > 0:
            return 1
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
