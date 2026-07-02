"""
LLM provider abstractions (SiliconFlow, Zhipu, Custom OpenAI-compatible)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
from pathlib import Path
from openai import OpenAI

# 尝试加载.env文件（如果存在）
# 注意：使用 override=False，这样环境变量（命令行设置的）会优先于 .env 文件
try:
    from dotenv import load_dotenv
    # 尝试从多个位置加载：1. VCG-Bench/.env  2. 项目根目录/.env
    vcgbench_root = Path(__file__).parent.parent.parent  # VCG-Bench目录
    project_root = vcgbench_root.parent  # 项目根目录
    env_loaded = False
    
    # 首先尝试从 VCG-Bench/.env 加载
    env_path = vcgbench_root / '.env'
    if env_path.exists():
        load_dotenv(env_path, override=False)
        env_loaded = True
    
    # 如果没找到，尝试从项目根目录加载
    if not env_loaded:
        env_path = project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path, override=False)
            env_loaded = True
except ImportError:
    pass  # dotenv未安装，跳过


class BaseProvider(ABC):
    """Base class for LLM providers"""

    def __init__(self):
        self.client: Optional[OpenAI] = None

    @abstractmethod
    def get_client(self) -> OpenAI:
        """Get the OpenAI-compatible client"""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default vision model for this provider"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that required environment variables are set"""
        pass


class SiliconFlowProvider(BaseProvider):
    """SiliconFlow provider"""

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv('SILICONFLOW_API_KEY')
        self.base_url = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
        self.default_model = os.getenv('SILICONFLOW_VISION_MODEL', 'Qwen/Qwen3-VL-30B-A3B-Instruct')

    def validate_config(self) -> bool:
        """Validate SiliconFlow configuration"""
        return bool(self.api_key)

    def get_client(self) -> OpenAI:
        """Get SiliconFlow OpenAI-compatible client"""
        if not self.client:
            if not self.validate_config():
                raise ValueError("SILICONFLOW_API_KEY not set in environment")
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self.client

    def get_default_model(self) -> str:
        """Get default SiliconFlow vision model"""
        return self.default_model


class ZhipuProvider(BaseProvider):
    """Zhipu GLM provider"""

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv('ZHIPU_API_KEY')
        self.base_url = os.getenv('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')
        self.default_model = os.getenv('ZHIPU_VISION_MODEL', 'glm-4v')

    def validate_config(self) -> bool:
        """Validate Zhipu configuration"""
        return bool(self.api_key)

    def get_client(self) -> OpenAI:
        """Get Zhipu OpenAI-compatible client"""
        if not self.client:
            if not self.validate_config():
                raise ValueError("ZHIPU_API_KEY not set in environment")
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self.client

    def get_default_model(self) -> str:
        """Get default Zhipu vision model"""
        return self.default_model


class CustomProvider(BaseProvider):
    """Custom OpenAI-compatible provider (e.g., Gemini via OpenRouter)"""

    def __init__(self):
        super().__init__()
        # 保存初始化时的值（从.env读取的默认值）
        self._default_api_key = os.getenv('CUSTOM_API_KEY')
        self._default_base_url = os.getenv('CUSTOM_BASE_URL')
        self.default_model = os.getenv('CUSTOM_VISION_MODEL', 'gpt-4-vision-preview')
        # 当前使用的值
        self._current_api_key = None
        self._current_base_url = None

    def _get_api_key(self) -> Optional[str]:
        """获取API key：优先使用环境变量，如果不存在则使用默认值"""
        return os.getenv('CUSTOM_API_KEY') or self._default_api_key

    def _get_base_url(self) -> Optional[str]:
        """获取base URL：优先使用环境变量，如果不存在则使用默认值"""
        base_url = os.getenv('CUSTOM_BASE_URL') or self._default_base_url
        if base_url:
            # 规范化 URL：移除末尾的斜杠，确保格式正确
            # OpenAI SDK 会自动添加路径，所以 base_url 不应该以斜杠结尾
            base_url = base_url.rstrip('/')
            # 确保 URL 格式正确（移除多余的斜杠，但保留协议后的双斜杠）
            # 例如：https://api.example.com//v1 -> https://api.example.com/v1
            if '://' in base_url:
                parts = base_url.split('://', 1)
                # 移除路径部分的多余斜杠
                parts[1] = parts[1].replace('//', '/')
                base_url = '://'.join(parts)
        return base_url

    def validate_config(self) -> bool:
        """Validate custom provider configuration"""
        api_key = self._get_api_key()
        base_url = self._get_base_url()
        return bool(api_key and base_url)

    def get_client(self) -> OpenAI:
        """Get custom OpenAI-compatible client (dynamically reads environment variables)"""
        # 每次调用时重新读取环境变量
        api_key = self._get_api_key()
        base_url = self._get_base_url()
        
        # Debug: 检查环境变量来源
        env_api_key = os.getenv('CUSTOM_API_KEY')
        env_base_url = os.getenv('CUSTOM_BASE_URL')
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"CustomProvider: env CUSTOM_BASE_URL={env_base_url}, using base_url={base_url}, from_default={base_url == self._default_base_url}")
        
        if not api_key or not base_url:
            raise ValueError("CUSTOM_API_KEY and CUSTOM_BASE_URL must be set in environment or .env file")
        
        # 如果环境变量或配置改变了，重新创建client
        if (not self.client or 
            self._current_api_key != api_key or 
            self._current_base_url != base_url):
            self._current_api_key = api_key
            self._current_base_url = base_url
            # 设置超时时间为20分钟（1200秒），适用于本地vLLM等慢速推理服务
            timeout = 1200.0  # 20 minutes in seconds
            # 禁用 OpenAI SDK 的自动重试，避免 524 错误时重复计费
            # 我们会在应用层处理重试逻辑，并可以检测 524 错误后立即失败
            max_retries = 0  # 禁用 SDK 自动重试
            logger.info(f"Creating OpenAI client with base_url={base_url}, timeout={timeout}s (20 minutes), max_retries={max_retries}")
            self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=max_retries)
        
        return self.client

    def get_default_model(self) -> str:
        """Get default custom vision model"""
        return self.default_model


class LocalProvider(BaseProvider):
    """Local model provider (e.g., Ollama, vLLM, LocalAI)"""

    def __init__(self):
        super().__init__()
        # 本地模型通常不需要API key，但有些实现可能需要
        self.api_key = os.getenv('LOCAL_API_KEY', 'ollama')  # Ollama默认不需要key
        self.base_url = os.getenv('LOCAL_BASE_URL', 'http://localhost:11434/v1')  # Ollama默认地址
        self.default_model = os.getenv('LOCAL_VISION_MODEL', 'llava')

    def validate_config(self) -> bool:
        """Validate local provider configuration"""
        # 本地模型只需要base_url，api_key可选
        return bool(self.base_url)

    def get_client(self) -> OpenAI:
        """Get local OpenAI-compatible client"""
        if not self.client:
            if not self.validate_config():
                raise ValueError("LOCAL_BASE_URL must be set in environment")
            # 对于本地模型，api_key可以为空或任意值
            # 设置超时时间为20分钟（1200秒），适用于本地vLLM等慢速推理服务
            timeout = 1200.0  # 20 minutes in seconds
            # 禁用 OpenAI SDK 的自动重试，避免 524 错误时重复计费
            max_retries = 0  # 禁用 SDK 自动重试
            self.client = OpenAI(
                api_key=self.api_key or 'ollama',
                base_url=self.base_url,
                timeout=timeout,
                max_retries=max_retries
            )
        return self.client

    def get_default_model(self) -> str:
        """Get default local vision model"""
        return self.default_model


def get_provider(provider_name: str) -> BaseProvider:
    """Factory function to get a provider by name"""
    providers = {
        'siliconflow': SiliconFlowProvider,
        'zhipu': ZhipuProvider,
        'custom': CustomProvider,
        'local': LocalProvider
    }

    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: {list(providers.keys())}")

    return provider_class()
