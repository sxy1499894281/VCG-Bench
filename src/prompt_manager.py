"""
Prompt 管理器 - 统一管理所有评估相关的 Prompt

设计目标：
1. Prompt 与代码逻辑完全分离
2. 支持版本管理和 A/B 测试
3. 支持从文件加载 Prompt（便于修改）
4. 提供统一的渲染接口
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptConfig:
    """Prompt 配置"""
    name: str
    default_version: str
    versions: Dict[str, str]
    description: Optional[str] = None


class PromptManager:
    """Prompt 管理器"""
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        初始化 Prompt 管理器
        
        Args:
            config_file: Prompt 配置文件路径（JSON 格式），如果为 None 则使用默认配置
        """
        self.config_file = config_file
        self.prompts: Dict[str, PromptConfig] = {}
        self._load_config()
    
    def _load_config(self):
        """加载 Prompt 配置"""
        if self.config_file and self.config_file.exists():
            # 从文件加载
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                self._load_from_dict(config_data)
                logger.info(f"Loaded prompts from {self.config_file}")
            except Exception as e:
                logger.warning(f"Failed to load prompt config from {self.config_file}: {e}, using defaults")
                self._load_defaults()
        else:
            # 使用默认配置（从 evaluation_prompts.py 导入）
            self._load_defaults()
    
    def _load_defaults(self):
        """加载默认配置"""
        try:
            # 尝试从 configs 目录导入
            import sys
            from pathlib import Path
            
            # 获取项目根目录
            current_file = Path(__file__)
            project_root = current_file.parent.parent  # VCG-Bench/
            configs_path = project_root / "configs"
            
            if str(configs_path) not in sys.path:
                sys.path.insert(0, str(configs_path))
            
            from evaluation_prompts import PROMPT_VERSIONS
            for name, config in PROMPT_VERSIONS.items():
                self.prompts[name] = PromptConfig(
                    name=name,
                    default_version=config["default"],
                    versions=config["versions"]
                )
        except ImportError as e:
            logger.warning(f"Failed to import default prompts: {e}, using empty config")
    
    def _load_from_dict(self, config_data: Dict[str, Any]):
        """从字典加载配置"""
        for name, config in config_data.items():
            self.prompts[name] = PromptConfig(
                name=name,
                default_version=config.get("default", "v1"),
                versions=config.get("versions", {}),
                description=config.get("description")
            )
    
    def get_prompt(
        self,
        prompt_name: str,
        version: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        获取并渲染 Prompt
        
        Args:
            prompt_name: Prompt 名称
            version: 版本号，如果为 None 则使用默认版本
            **kwargs: 模板变量
        
        Returns:
            渲染后的 Prompt 字符串
        """
        if prompt_name not in self.prompts:
            raise ValueError(f"Unknown prompt name: {prompt_name}. Available: {list(self.prompts.keys())}")
        
        config = self.prompts[prompt_name]
        version = version or config.default_version
        
        if version not in config.versions:
            raise ValueError(f"Unknown version '{version}' for prompt '{prompt_name}'. Available: {list(config.versions.keys())}")
        
        template = config.versions[version]
        
        # 渲染模板
        return self._render_template(template, **kwargs)
    
    def _render_template(self, template: str, **kwargs) -> str:
        """
        渲染模板（支持简单的 {{ variable }} 格式）
        
        Args:
            template: 模板字符串
            **kwargs: 模板变量
        
        Returns:
            渲染后的字符串
        """
        result = template
        
        # 替换 {{ variable }} 格式
        for key, value in kwargs.items():
            # 支持 {{ key }} 和 {{key}} 两种格式
            for placeholder in [f"{{{{ {key} }}}}", f"{{{{{key}}}}}"]:
                result = result.replace(placeholder, str(value))
        
        return result
    
    def list_prompts(self) -> Dict[str, PromptConfig]:
        """列出所有可用的 Prompt"""
        return self.prompts.copy()
    
    def add_prompt(
        self,
        name: str,
        template: str,
        version: str = "v1",
        set_as_default: bool = False
    ):
        """
        动态添加 Prompt（运行时修改）
        
        Args:
            name: Prompt 名称
            template: Prompt 模板
            version: 版本号
            set_as_default: 是否设置为默认版本
        """
        if name not in self.prompts:
            self.prompts[name] = PromptConfig(
                name=name,
                default_version=version if set_as_default else "v1",
                versions={version: template}
            )
        else:
            config = self.prompts[name]
            config.versions[version] = template
            if set_as_default:
                config.default_version = version
    
    def save_config(self, output_file: Path):
        """保存配置到文件"""
        config_data = {}
        for name, config in self.prompts.items():
            config_data[name] = {
                "default": config.default_version,
                "versions": config.versions,
                "description": config.description
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved prompt config to {output_file}")


# 全局单例
_default_manager: Optional[PromptManager] = None


def get_prompt_manager(config_file: Optional[Path] = None) -> PromptManager:
    """
    获取全局 Prompt 管理器实例
    
    Args:
        config_file: 配置文件路径，仅在首次调用时生效
    
    Returns:
        PromptManager 实例
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = PromptManager(config_file)
    return _default_manager


# 便捷函数
def get_prompt(prompt_name: str, version: Optional[str] = None, **kwargs) -> str:
    """
    便捷函数：获取并渲染 Prompt
    
    Args:
        prompt_name: Prompt 名称
        version: 版本号
        **kwargs: 模板变量
    
    Returns:
        渲染后的 Prompt 字符串
    """
    manager = get_prompt_manager()
    return manager.get_prompt(prompt_name, version, **kwargs)

