#!/usr/bin/env python3
"""
Task 1: Interactive filter for Gemini results
交互式筛选工具，用于筛选Gemini生成的结果
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task1_filter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_sample(sample_dir: Path, model_name: str = None) -> dict:
    """
    加载样本数据
    
    Args:
        sample_dir: 样本目录
        model_name: 模型名称，如果为None则使用默认模型（gemini-3-pro-preview）
        
    Returns:
        样本数据字典
    """
    sample_data = {
        "sample_id": sample_dir.name,
        "sample_path": str(sample_dir),
        "original": None,
        "description": None,
        "xml": None,
        "rendered": None,
        "screening_status": None
    }
    
    # 查找模型目录
    model_dir = None
    if model_name:
        candidate_dir = sample_dir / f"model_{model_name}"
        if candidate_dir.exists():
            model_dir = candidate_dir
    else:
        # 如果没有指定模型，优先查找 gemini-3-pro-preview
        desc_model_name = "gemini-3-pro-preview"
        candidate_dir = sample_dir / f"model_{desc_model_name}"
        if candidate_dir.exists():
            model_dir = candidate_dir
        else:
            # 查找其他包含"gemini"的模型目录
            for m_dir in sample_dir.glob('model_*'):
                if 'gemini' in m_dir.name.lower():
                    model_dir = m_dir
                    break
    
    if model_dir is None or not model_dir.exists():
        return None
    
    # 原始图片
    original_path = sample_dir / "original.png"
    if original_path.exists():
        sample_data["original"] = str(original_path)
    
    # 描述
    desc_path = model_dir / "llm_description.txt"
    if desc_path.exists():
        with open(desc_path, 'r', encoding='utf-8') as f:
            sample_data["description"] = f.read()[:500]  # 只显示前500字符
    
    # XML
    xml_path = model_dir / "diagram.xml"
    if xml_path.exists():
        with open(xml_path, 'r', encoding='utf-8') as f:
            sample_data["xml"] = f.read()[:500]  # 只显示前500字符
    
    # 渲染图
    rendered_path = model_dir / "rendered.png"
    if rendered_path.exists():
        sample_data["rendered"] = str(rendered_path)
    
    # 筛选状态
    status_path = model_dir / "screening_status.json"
    if status_path.exists():
        with open(status_path, 'r', encoding='utf-8') as f:
            sample_data["screening_status"] = json.load(f)
    
    return sample_data


def open_image(image_path: str):
    """
    打开图片（使用系统默认程序）
    
    Args:
        image_path: 图片路径
    """
    import subprocess
    import platform
    
    if not image_path or not Path(image_path).exists():
        return False
    
    try:
        if platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', image_path], check=True)
        elif platform.system() == 'Linux':
            subprocess.run(['xdg-open', image_path], check=True)
        elif platform.system() == 'Windows':
            subprocess.run(['start', image_path], shell=True, check=True)
        return True
    except Exception as e:
        logger.warning(f"Failed to open image: {e}")
        return False


def display_sample(sample_data: dict, index: int, total: int, auto_open_images: bool = True):
    """
    显示样本信息
    
    Args:
        sample_data: 样本数据
        index: 当前索引
        total: 总数
        auto_open_images: 是否自动打开图片
    """
    print("\n" + "=" * 80)
    print(f"Sample {index}/{total}: {sample_data['sample_id']}")
    print("=" * 80)
    
    # 显示状态
    status = sample_data.get('screening_status', {})
    current_status = status.get('status', 'pending')
    print(f"Current status: {current_status}")
    
    # 显示文件路径
    original_path = sample_data.get('original')
    rendered_path = sample_data.get('rendered')
    
    print(f"\nOriginal image: {original_path or 'N/A'}")
    print(f"Rendered image: {rendered_path or 'N/A'}")
    
    # 自动打开图片（如果启用）
    if auto_open_images:
        if original_path:
            print("\nOpening original image...")
            open_image(original_path)
        if rendered_path:
            print("Opening rendered image...")
            open_image(rendered_path)
    
    # 显示描述预览
    if sample_data.get('description'):
        print(f"\nDescription preview:")
        print("-" * 80)
        print(sample_data['description'])
        print("-" * 80)
    
    # 显示XML预览
    if sample_data.get('xml'):
        print(f"\nXML preview:")
        print("-" * 80)
        print(sample_data['xml'])
        print("-" * 80)
    
    print("\nOptions:")
    print("  [y/Enter] - Approve (标记为approved)")
    print("  [n] - Reject (标记为rejected)")
    print("  [s] - Skip (保持pending，稍后处理)")
    print("  [q] - Quit and save progress")
    print("  [p] - Previous sample")
    print("  [o] - Open original image")
    print("  [r] - Open rendered image")


def update_screening_status(sample_dir: Path, status: str, notes: str = None, model_name: str = None):
    """
    更新筛选状态
    
    Args:
        sample_dir: 样本目录
        status: 状态 (approved/rejected/pending)
        notes: 备注
        model_name: 模型名称，如果为None则使用默认模型
    """
    # 查找模型目录
    model_dir = None
    if model_name:
        candidate_dir = sample_dir / f"model_{model_name}"
        if candidate_dir.exists():
            model_dir = candidate_dir
    else:
        # 如果没有指定模型，优先查找 gemini-3-pro-preview
        desc_model_name = "gemini-3-pro-preview"
        candidate_dir = sample_dir / f"model_{desc_model_name}"
        if candidate_dir.exists():
            model_dir = candidate_dir
        else:
            # 查找其他包含"gemini"的模型目录
            for m_dir in sample_dir.glob('model_*'):
                if 'gemini' in m_dir.name.lower():
                    model_dir = m_dir
                    break
    
    if model_dir is None:
        logger.error(f"Model directory not found for {sample_dir.name}")
        return
    
    status_path = model_dir / "screening_status.json"
    
    screening_status = {
        "status": status,
        "screened_date": datetime.now().isoformat(),
        "screener_notes": notes
    }
    
    with open(status_path, 'w', encoding='utf-8') as f:
        json.dump(screening_status, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Updated screening status for {sample_dir.name}: {status}")


def find_pending_samples(source_dir: Path, model_name: str = None) -> list:
    """
    查找待筛选的样本
    
    Args:
        source_dir: task1_benchmark目录
        model_name: 模型名称，如果为None则使用默认模型
        
    Returns:
        待筛选样本列表
    """
    pending_samples = []
    
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            # 查找模型目录
            model_dir = None
            if model_name:
                candidate_dir = sample_dir / f"model_{model_name}"
                if candidate_dir.exists():
                    model_dir = candidate_dir
            else:
                # 如果没有指定模型，优先查找 gemini-3-pro-preview
                desc_model_name = "gemini-3-pro-preview"
                candidate_dir = sample_dir / f"model_{desc_model_name}"
                if candidate_dir.exists():
                    model_dir = candidate_dir
                else:
                    # 查找其他包含"gemini"的模型目录
                    for m_dir in sample_dir.glob('model_*'):
                        if 'gemini' in m_dir.name.lower():
                            model_dir = m_dir
                            break
            
            if model_dir is None:
                continue
            
            status_path = model_dir / "screening_status.json"
            
            if not status_path.exists():
                pending_samples.append(sample_dir)
                continue
            
            with open(status_path, 'r', encoding='utf-8') as f:
                status = json.load(f)
                if status.get('status') == 'pending':
                    pending_samples.append(sample_dir)
    
    return sorted(pending_samples)


def review_samples(source_dir: Path, start_index: int = 0, auto_open_images: bool = True, model_name: str = None):
    """
    交互式筛选样本
    
    Args:
        source_dir: task1_benchmark目录
        start_index: 起始索引
        auto_open_images: 是否自动打开图片
        model_name: 模型名称，如果为None则使用默认模型
    """
    logger.info("=" * 80)
    logger.info("Task 1: Interactive Filter for Model Results")
    if model_name:
        logger.info(f"Model: {model_name}")
    logger.info("=" * 80)
    
    # 查找待筛选样本
    pending_samples = find_pending_samples(source_dir, model_name=model_name)
    logger.info(f"Found {len(pending_samples)} pending samples")
    
    if not pending_samples:
        logger.info("No pending samples to review")
        return
    
    current_index = start_index
    total = len(pending_samples)
    
    while current_index < total:
        sample_dir = pending_samples[current_index]
        sample_data = load_sample(sample_dir, model_name=model_name)
        
        if not sample_data:
            logger.warning(f"Failed to load sample {sample_dir.name}, skipping")
            current_index += 1
            continue
        
        display_sample(sample_data, current_index + 1, total, auto_open_images=auto_open_images)
        
        try:
            choice = input("\nYour choice: ").strip().lower()
            
            if choice in ['y', '']:
                # Approve
                notes = input("Notes (optional, press Enter to skip): ").strip() or None
                update_screening_status(sample_dir, 'approved', notes, model_name=model_name)
                current_index += 1
                
            elif choice == 'n':
                # Reject
                notes = input("Rejection reason (optional, press Enter to skip): ").strip() or None
                update_screening_status(sample_dir, 'rejected', notes, model_name=model_name)
                current_index += 1
                
            elif choice == 's':
                # Skip
                current_index += 1
                
            elif choice == 'q':
                # Quit
                logger.info(f"Stopped at sample {current_index + 1}/{total}")
                break
                
            elif choice == 'p':
                # Previous
                if current_index > 0:
                    current_index -= 1
                else:
                    print("Already at first sample")
                    
            elif choice == 'o':
                # Open original image
                if sample_data.get('original'):
                    open_image(sample_data['original'])
                continue
                
            elif choice == 'r':
                # Open rendered image
                if sample_data.get('rendered'):
                    open_image(sample_data['rendered'])
                continue
                
            else:
                print("Invalid choice, please try again")
                
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
            break
        except Exception as e:
            logger.error(f"Error processing choice: {e}", exc_info=True)
            current_index += 1
    
    # 统计
    logger.info("\n" + "=" * 80)
    logger.info("Review Summary")
    logger.info("=" * 80)
    
    # 统计approved和rejected
    approved = 0
    rejected = 0
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            # 查找模型目录
            model_dir = None
            if model_name:
                candidate_dir = sample_dir / f"model_{model_name}"
                if candidate_dir.exists():
                    model_dir = candidate_dir
            else:
                desc_model_name = "gemini-3-pro-preview"
                candidate_dir = sample_dir / f"model_{desc_model_name}"
                if candidate_dir.exists():
                    model_dir = candidate_dir
                else:
                    for m_dir in sample_dir.glob('model_*'):
                        if 'gemini' in m_dir.name.lower():
                            model_dir = m_dir
                            break
            if model_dir is None:
                continue
            status_path = model_dir / "screening_status.json"
            if status_path.exists():
                status = json.load(open(status_path))
                if status.get('status') == 'approved':
                    approved += 1
                elif status.get('status') == 'rejected':
                    rejected += 1
    pending = len(find_pending_samples(source_dir, model_name=model_name))
    
    logger.info(f"Approved: {approved}")
    logger.info(f"Rejected: {rejected}")
    logger.info(f"Pending: {pending}")
    logger.info(f"Total reviewed: {approved + rejected}")


def show_status(source_dir: Path, model_name: str = None):
    """
    显示筛选进度
    
    Args:
        source_dir: task1_benchmark目录
        model_name: 模型名称，如果为None则使用默认模型
    """
    logger.info("=" * 80)
    logger.info("Screening Status")
    if model_name:
        logger.info(f"Model: {model_name}")
    logger.info("=" * 80)
    
    all_samples = []
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        for sample_dir in domain_dir.glob('sample_*'):
            if sample_dir.is_dir():
                all_samples.append(sample_dir)
    
    approved = 0
    rejected = 0
    pending = 0
    
    for sample_dir in all_samples:
        # 查找模型目录
        model_dir = None
        if model_name:
            candidate_dir = sample_dir / f"model_{model_name}"
            if candidate_dir.exists():
                model_dir = candidate_dir
        else:
            desc_model_name = "gemini-3-pro-preview"
            candidate_dir = sample_dir / f"model_{desc_model_name}"
            if candidate_dir.exists():
                model_dir = candidate_dir
            else:
                for m_dir in sample_dir.glob('model_*'):
                    if 'gemini' in m_dir.name.lower():
                        model_dir = m_dir
                        break
        
        if model_dir is None:
            pending += 1
            continue
        
        status_path = model_dir / "screening_status.json"
        if not status_path.exists():
            pending += 1
            continue
        
        with open(status_path, 'r', encoding='utf-8') as f:
            status = json.load(f)
            status_val = status.get('status', 'pending')
            if status_val == 'approved':
                approved += 1
            elif status_val == 'rejected':
                rejected += 1
            else:
                pending += 1
    
    total = len(all_samples)
    logger.info(f"Total samples: {total}")
    logger.info(f"Approved: {approved} ({approved/total*100:.1f}%)" if total > 0 else "Approved: 0")
    logger.info(f"Rejected: {rejected} ({rejected/total*100:.1f}%)" if total > 0 else "Rejected: 0")
    logger.info(f"Pending: {pending} ({pending/total*100:.1f}%)" if total > 0 else "Pending: 0")


def start_web_server(source_dir: Path, host: str = '127.0.0.1', port: int = 5000):
    """
    启动web服务器
    
    Args:
        source_dir: task1_benchmark目录
        host: 主机地址
        port: 端口号
    """
    try:
        # 检查Flask是否安装
        try:
            import flask
        except ImportError:
            logger.error("=" * 80)
            logger.error("Flask is not installed!")
            logger.error("=" * 80)
            logger.error("Please install Flask to use the web interface:")
            logger.error("  pip install flask")
            logger.error("")
            logger.error("Or use CLI mode instead:")
            logger.error("  python scripts/task1/filter.py review --source <dir> --cli")
            return 1
        
        # 使用相对导入
        import importlib.util
        web_app_path = Path(__file__).parent / 'web_screening_app.py'
        spec = importlib.util.spec_from_file_location("web_screening_app", web_app_path)
        web_screening_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(web_screening_app)
        
        # 尝试启动服务器，如果端口被占用则尝试其他端口
        import socket
        original_port = port
        max_attempts = 10
        
        for attempt in range(max_attempts):
            # 检查端口是否可用
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:  # 端口可用
                break
            
            # 端口被占用，尝试下一个端口
            if attempt == 0:
                logger.warning(f"Port {port} is already in use, trying alternative ports...")
            port += 1
        
        if result == 0:  # 所有尝试的端口都被占用
            logger.error(f"Could not find an available port after {max_attempts} attempts")
            logger.error("Please free up a port or specify a different port with --port")
            return 1
        
        if port != original_port:
            logger.warning(f"Using port {port} instead of {original_port}")
        
        # 查找评估结果目录
        evaluation_dir = source_dir.parent / "task1_evaluation"
        if not evaluation_dir.exists():
            evaluation_dir = None
        
        logger.info("=" * 80)
        logger.info("Starting Web Screening Interface")
        logger.info("=" * 80)
        logger.info(f"Source directory: {source_dir}")
        if evaluation_dir:
            logger.info(f"Evaluation directory: {evaluation_dir}")
        logger.info(f"Server will start at http://{host}:{port}")
        logger.info("Press Ctrl+C to stop the server")
        
        web_screening_app.run_server(str(source_dir), host=host, port=port, evaluation_dir=str(evaluation_dir) if evaluation_dir else None)
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Task 1: Interactive filter for Gemini results"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Review command - Web界面（默认）或命令行界面
    review_parser = subparsers.add_parser('review', help='Start web review interface (default) or CLI')
    review_parser.add_argument('--source', type=Path, required=True,
                               help='Source directory (task1_benchmark)')
    review_parser.add_argument('--cli', action='store_true',
                              help='Use CLI interface instead of web (default: web)')
    review_parser.add_argument('--host', type=str, default='127.0.0.1',
                              help='Host address for web interface (default: 127.0.0.1)')
    review_parser.add_argument('--port', type=int, default=5000,
                              help='Port number for web interface (default: 5000)')
    review_parser.add_argument('--no-auto-open', action='store_true',
                              help='Do not automatically open images (CLI mode only)')
    review_parser.add_argument('--model', type=str, default=None,
                              help='Model name to review (e.g., gemini-3-pro-preview)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show screening status')
    status_parser.add_argument('--source', type=Path, required=True,
                               help='Source directory (task1_benchmark)')
    status_parser.add_argument('--model', type=str, default=None,
                              help='Model name to show status for (e.g., gemini-3-pro-preview)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'review':
        if not args.source.exists():
            logger.error(f"Source directory not found: {args.source}")
            return 1
        if args.cli:
            # 交互式命令行界面模式
            review_samples(args.source, auto_open_images=not args.no_auto_open, model_name=args.model)
            return 0
        else:
            # Web界面模式（默认）
            # 注意：Web界面支持在界面上切换模型，不需要在这里传递model参数
            return start_web_server(args.source, args.host, args.port)
        
    elif args.command == 'status':
        if not args.source.exists():
            logger.error(f"Source directory not found: {args.source}")
            return 1
        show_status(args.source, model_name=args.model)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
