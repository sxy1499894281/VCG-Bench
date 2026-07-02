#!/usr/bin/env python3
"""
Task 2: Viewer for Task 2 Data
查看和编辑 Task 2 数据的工具
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Setup logging
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task2_viewer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def show_status(source_dir: Path):
    """
    显示查看状态
    
    Args:
        source_dir: task2_benchmark目录
    """
    logger.info("=" * 80)
    logger.info("Task 2 Viewer Status")
    logger.info("=" * 80)
    
    total_samples = 0
    total_instructions = 0
    
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            total_samples += 1
            instructions_dir = sample_dir / "instructions"
            if instructions_dir.exists():
                for inst_dir in instructions_dir.glob('inst_*'):
                    if inst_dir.is_dir():
                        total_instructions += 1
    
    logger.info(f"Total samples: {total_samples}")
    logger.info(f"Total instructions: {total_instructions}")


def start_web_server(source_dir: Path, evaluation_dir: Path = None, host: str = '127.0.0.1', port: int = 5000):
    """
    启动web服务器
    
    Args:
        source_dir: task2_benchmark目录
        evaluation_dir: task2_evaluation目录（可选）
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
            return 1
        
        # 使用相对导入
        import importlib.util
        web_app_path = Path(__file__).parent / 'web_viewer_app.py'
        spec = importlib.util.spec_from_file_location("web_viewer_app", web_app_path)
        web_viewer_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(web_viewer_app)
        
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
        
        logger.info("=" * 80)
        logger.info("Starting Task 2 Viewer Interface")
        logger.info("=" * 80)
        logger.info(f"Source directory: {source_dir}")
        if evaluation_dir:
            logger.info(f"Evaluation directory: {evaluation_dir}")
        logger.info(f"Server will start at http://{host}:{port}")
        logger.info("Press Ctrl+C to stop the server")
        
        web_viewer_app.run_server(
            str(source_dir), 
            host=host, 
            port=port, 
            evaluation_dir=str(evaluation_dir) if evaluation_dir else None
        )
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error starting server: {e}", exc_info=True)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Task 2: Viewer for Task 2 Data"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Review command - Web界面
    review_parser = subparsers.add_parser('review', help='Start web review interface')
    review_parser.add_argument('--source', type=Path, required=True,
                               help='Source directory (task2_benchmark)')
    review_parser.add_argument('--evaluation', type=Path, default=None,
                               help='Evaluation directory (task2_evaluation, optional)')
    review_parser.add_argument('--host', type=str, default='127.0.0.1',
                              help='Host address for web interface (default: 127.0.0.1)')
    review_parser.add_argument('--port', type=int, default=5000,
                              help='Port number for web interface (default: 5000)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show viewing status')
    status_parser.add_argument('--source', type=Path, required=True,
                               help='Source directory (task2_benchmark)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'review':
        if not args.source.exists():
            logger.error(f"Source directory not found: {args.source}")
            return 1
        
        evaluation_dir = args.evaluation
        if evaluation_dir and not evaluation_dir.exists():
            logger.warning(f"Evaluation directory not found: {evaluation_dir}, continuing without it")
            evaluation_dir = None
        
        return start_web_server(args.source, evaluation_dir, args.host, args.port)
        
    elif args.command == 'status':
        if not args.source.exists():
            logger.error(f"Source directory not found: {args.source}")
            return 1
        show_status(args.source)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
