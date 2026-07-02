#!/usr/bin/env python3
"""
从HuggingFace批量下载模型的脚本（使用hf-mirror.com代理）

使用方法:
    python download_models.py

配置:
    在脚本开头的 MODEL_LIST 中配置要下载的模型列表
    在 SAVE_DIR 中配置模型保存目录
    在 HF_MIRROR 中配置镜像地址
"""

import os
import sys
import time
import threading
from pathlib import Path
from huggingface_hub import snapshot_download
import logging

# ==================== 配置区域 ====================
# 要下载的模型列表（格式：HuggingFace模型ID）
MODEL_LIST = [
    "llava-hf/llava-1.5-7b-hf",
    # 添加更多模型...
    # "model-org/model-name",
]

# 模型保存目录（相对于脚本所在目录）
# 默认保存到: VCG-Bench/models/huggingface/
SCRIPT_DIR = Path(__file__).parent.parent.parent.parent
SAVE_DIR = SCRIPT_DIR / "models" / "huggingface"

# HuggingFace镜像地址（使用hf-mirror.com代理）
HF_MIRROR = "https://hf-mirror.com"

# 日志配置
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
# ==================== 配置区域结束 ====================

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "huggingface_download.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_dir_size(path: Path) -> int:
    """获取目录大小（字节）"""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def monitor_download_progress(model_save_dir: Path, model_id: str, stop_event: threading.Event):
    """监控下载进度，定期输出状态"""
    last_size = 0
    last_time = time.time()
    check_interval = 10  # 每10秒检查一次
    no_progress_count = 0  # 连续无进度计数
    
    while not stop_event.is_set():
        time.sleep(check_interval)
        
        if stop_event.is_set():
            break
            
        current_size = get_dir_size(model_save_dir)
        current_time = time.time()
        elapsed = current_time - last_time
        
        if elapsed > 0:
            size_diff = current_size - last_size
            speed = size_diff / elapsed if elapsed > 0 else 0
            speed_str = format_size(speed) + "/s"
            
            # 检查是否有进度
            if size_diff > 1024:  # 至少1KB的变化才算有进度
                no_progress_count = 0
            else:
                no_progress_count += 1
        else:
            speed_str = "计算中..."
        
        if current_size > 0:
            logger.info(f"  📥 下载中... 已下载: {format_size(current_size)} | 速度: {speed_str}")
            
            # 如果连续3次检查都没有进度，提示用户
            if no_progress_count >= 3:
                logger.info(f"  ⏳ 下载速度较慢或暂停中，请耐心等待...")
                no_progress_count = 0  # 重置计数，避免重复提示
        
        last_size = current_size
        last_time = current_time


def setup_hf_mirror():
    """
    配置HuggingFace镜像环境变量
    """
    # 设置HF_ENDPOINT环境变量以使用镜像
    os.environ["HF_ENDPOINT"] = HF_MIRROR
    logger.info(f"已配置HuggingFace镜像: {HF_MIRROR}")


def download_model(model_id: str, save_dir: Path) -> bool:
    """
    下载单个模型
    
    Args:
        model_id: HuggingFace模型ID
        save_dir: 保存目录
        
    Returns:
        bool: 下载是否成功
    """
    try:
        logger.info(f"开始下载模型: {model_id}")
        
        # 创建模型保存目录（使用模型ID作为子目录名）
        model_save_dir = save_dir / model_id.replace("/", "_")
        model_save_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录开始时间和初始大小
        start_time = time.time()
        initial_size = get_dir_size(model_save_dir)
        
        if initial_size > 0:
            logger.info(f"  检测到已存在文件，大小: {format_size(initial_size)}")
            logger.info(f"  将续传下载...")
        
        # 启动进度监控线程
        stop_event = threading.Event()
        progress_thread = threading.Thread(
            target=monitor_download_progress,
            args=(model_save_dir, model_id, stop_event),
            daemon=True
        )
        progress_thread.start()
        
        try:
            # 下载模型
            logger.info(f"  正在连接镜像服务器并开始下载...")
            logger.info(f"  提示: 每10秒会输出一次下载进度，请耐心等待...")
            cache_dir = snapshot_download(
                repo_id=model_id,
                local_dir=str(model_save_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
            )
            
            # 停止进度监控
            stop_event.set()
            progress_thread.join(timeout=2)
            
            # 计算最终统计
            end_time = time.time()
            elapsed_time = end_time - start_time
            final_size = get_dir_size(model_save_dir)
            downloaded_size = final_size - initial_size
            
            logger.info(f"✓ 模型下载完成: {model_id}")
            logger.info(f"  保存路径: {model_save_dir}")
            logger.info(f"  总大小: {format_size(final_size)}")
            if downloaded_size > 0:
                logger.info(f"  本次下载: {format_size(downloaded_size)}")
                logger.info(f"  耗时: {elapsed_time/60:.1f} 分钟 ({elapsed_time:.1f} 秒)")
                if elapsed_time > 0:
                    avg_speed = downloaded_size / elapsed_time
                    logger.info(f"  平均速度: {format_size(avg_speed)}/s")
            
            return True
            
        except KeyboardInterrupt:
            logger.warning(f"  下载被用户中断: {model_id}")
            stop_event.set()
            raise
        except Exception as e:
            stop_event.set()
            raise e
            
    except KeyboardInterrupt:
        logger.warning(f"✗ 下载被用户中断: {model_id}")
        return False
    except Exception as e:
        logger.error(f"✗ 下载模型失败: {model_id}")
        logger.error(f"  错误信息: {str(e)}")
        logger.error(f"  错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"  详细错误:\n{traceback.format_exc()}")
        return False


def main():
    """主函数"""
    total_start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("HuggingFace 模型批量下载工具（使用hf-mirror.com代理）")
    logger.info("=" * 60)
    
    # 配置镜像
    setup_hf_mirror()
    
    logger.info(f"保存目录: {SAVE_DIR}")
    logger.info(f"待下载模型数量: {len(MODEL_LIST)}")
    logger.info(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    logger.info("提示: 下载过程中会定期输出进度信息")
    logger.info("      如果长时间没有输出，可能是网络较慢，请耐心等待...")
    logger.info("")
    
    # 确保保存目录存在
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 统计信息
    success_count = 0
    fail_count = 0
    
    # 逐个下载模型
    for i, model_id in enumerate(MODEL_LIST, 1):
        logger.info(f"[{i}/{len(MODEL_LIST)}] 处理模型: {model_id}")
        logger.info("-" * 60)
        
        model_start_time = time.time()
        if download_model(model_id, SAVE_DIR):
            success_count += 1
            model_elapsed = time.time() - model_start_time
            logger.info(f"✓ 模型 {model_id} 下载成功，耗时: {model_elapsed/60:.1f}分钟")
        else:
            fail_count += 1
            logger.error(f"✗ 模型 {model_id} 下载失败")
        
        logger.info("")  # 空行分隔
    
    # 输出统计信息
    total_elapsed_time = time.time() - total_start_time
    total_elapsed_minutes = total_elapsed_time / 60
    
    logger.info("=" * 60)
    logger.info("下载完成统计")
    logger.info("=" * 60)
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {fail_count} 个")
    logger.info(f"总计: {len(MODEL_LIST)} 个")
    logger.info(f"总耗时: {total_elapsed_minutes:.1f}分钟 ({total_elapsed_time:.1f}秒)")
    logger.info(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    if fail_count > 0:
        logger.warning("部分模型下载失败，请检查日志文件")
        sys.exit(1)
    else:
        logger.info("所有模型下载成功！")


if __name__ == "__main__":
    main()

