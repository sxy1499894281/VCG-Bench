#!/usr/bin/env python3
"""
临时脚本：使用 hf-mirror 下载 SigLIP 模型
Usage:
    python scripts/download_siglip_model.py
    python scripts/download_siglip_model.py --model google/siglip2-so400m-patch16-512
"""

import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def download_siglip_model(model_name: str = "google/siglip2-giant-opt-patch16-384", use_mirror: bool = True):
    """
    下载 SigLIP 模型
    
    Args:
        model_name: 模型名称
        use_mirror: 是否使用 hf-mirror 镜像
    """
    # 设置 HuggingFace 镜像（如果需要）
    if use_mirror:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print(f"✅ 已设置 HuggingFace 镜像: {os.environ['HF_ENDPOINT']}")
    else:
        # 使用官方源
        if "HF_ENDPOINT" in os.environ:
            del os.environ["HF_ENDPOINT"]
        print("✅ 使用 HuggingFace 官方源")
    
    print(f"\n📦 开始下载模型: {model_name}")
    print("=" * 60)
    
    try:
        from transformers import SiglipModel, SiglipProcessor
        import torch
        
        print(f"\n1️⃣ 下载 Processor (处理器)...")
        # 移除 resume_download 参数（已弃用，默认会自动恢复下载）
        # 添加 use_fast=True 以使用快速处理器，消除警告
        processor = SiglipProcessor.from_pretrained(
            model_name,
            cache_dir=None,  # 使用默认缓存目录
            use_fast=True  # 使用快速处理器，消除警告
        )
        print(f"   ✅ Processor 下载完成")
        
        print(f"\n2️⃣ 下载 Model (模型)...")
        # 移除 resume_download 参数（已弃用，默认会自动恢复下载）
        model = SiglipModel.from_pretrained(
            model_name,
            cache_dir=None  # 使用默认缓存目录
        )
        print(f"   ✅ Model 下载完成")
        
        # 检查模型信息
        print(f"\n3️⃣ 模型信息:")
        print(f"   - 模型名称: {model_name}")
        print(f"   - 模型类型: {type(model).__name__}")
        
        # 检查设备
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"   - 可用设备: {device}")
        
        # 获取缓存目录
        try:
            from transformers.utils import TRANSFORMERS_CACHE
            cache_dir = TRANSFORMERS_CACHE if TRANSFORMERS_CACHE else os.path.expanduser("~/.cache/huggingface/transformers")
        except:
            cache_dir = os.path.expanduser("~/.cache/huggingface/transformers")
        print(f"   - 缓存目录: {cache_dir}")
        
        # 检查模型文件大小（如果可能）
        try:
            model_size = sum(p.numel() for p in model.parameters())
            print(f"   - 参数量: {model_size / 1e6:.2f}M")
        except:
            pass
        
        print(f"\n✅ 模型下载完成！")
        print(f"   模型已保存到: {cache_dir}")
        print(f"\n💡 提示: 现在可以在代码中使用 '{model_name}' 作为模型检查点")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ 导入错误: {e}")
        print(f"\n请先安装依赖:")
        print(f"   pip install transformers torch")
        return False
        
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        print(f"\n可能的原因:")
        print(f"   1. 模型名称不存在: {model_name}")
        print(f"   2. 网络连接问题")
        print(f"   3. 镜像服务器问题")
        print(f"\n💡 建议:")
        print(f"   1. 检查模型名称是否正确")
        print(f"   2. 尝试不使用镜像: --no-mirror")
        print(f"   3. 检查网络连接")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="下载 SigLIP 模型（支持 hf-mirror 镜像）"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="google/siglip2-so400m-patch16-512",
        help="模型名称 (默认: google/siglip2-so400m-patch16-512)"
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="不使用 hf-mirror 镜像，使用官方源"
    )
    
    args = parser.parse_args()
    
    # 获取脚本所在目录，用于创建日志文件
    script_dir = Path(__file__).parent
    
    print("=" * 60)
    print("SigLIP 模型下载脚本")
    print("=" * 60)
    print(f"日志文件: {script_dir}/download_siglip_model.log")
    print("=" * 60)
    
    success = download_siglip_model(
        model_name=args.model,
        use_mirror=not args.no_mirror
    )
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 下载成功！")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ 下载失败！")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

