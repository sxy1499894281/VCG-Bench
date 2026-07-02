"""
Settings and configuration management
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """
    Global settings for image-to-diagram pipeline
    Load from environment variables and provide defaults
    """

    # LLM Provider settings
    siliconflow_api_key: Optional[str] = field(default_factory=lambda: os.getenv('SILICONFLOW_API_KEY'))
    siliconflow_base_url: str = field(default_factory=lambda: os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1'))
    siliconflow_model: str = field(default_factory=lambda: os.getenv('SILICONFLOW_VISION_MODEL', 'Qwen/Qwen3-VL-30B-A3B-Instruct'))

    zhipu_api_key: Optional[str] = field(default_factory=lambda: os.getenv('ZHIPU_API_KEY'))
    zhipu_base_url: str = field(default_factory=lambda: os.getenv('ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4'))
    zhipu_model: str = field(default_factory=lambda: os.getenv('ZHIPU_VISION_MODEL', 'glm-4v'))

    custom_api_key: Optional[str] = field(default_factory=lambda: os.getenv('CUSTOM_API_KEY'))
    custom_base_url: Optional[str] = field(default_factory=lambda: os.getenv('CUSTOM_BASE_URL'))
    custom_model: str = field(default_factory=lambda: os.getenv('CUSTOM_VISION_MODEL', 'gpt-4-vision-preview'))

    # Default LLM settings
    default_provider: str = 'custom'
    default_temperature: float = 0.0
    default_max_tokens: int = 4096

    # Screening settings
    screening_threshold: float = 0.6
    screening_top_n: int = 10

    # Processing settings
    enable_diagram_generation: bool = False
    enable_diagram_rendering: bool = False
    max_repair_attempts: int = 3

    # Paths
    data_dir: Path = field(default_factory=lambda: Path('data'))
    input_dir: Path = field(default_factory=lambda: Path('data/input'))
    intermediate_dir: Path = field(default_factory=lambda: Path('data/intermediate'))
    output_dir: Path = field(default_factory=lambda: Path('data'))
    logs_dir: Path = field(default_factory=lambda: Path('logs'))

    # Drawio renderer
    drawio_path: Optional[Path] = None
    render_backend: str = 'drawio-cli'

    # Logging
    log_level: str = 'INFO'
    log_to_file: bool = True

    def __post_init__(self):
        """Validate settings after initialization"""
        # Convert string paths to Path objects
        self.data_dir = Path(self.data_dir)
        self.input_dir = Path(self.input_dir)
        self.intermediate_dir = Path(self.intermediate_dir)
        self.output_dir = Path(self.output_dir)
        self.logs_dir = Path(self.logs_dir)

        if self.drawio_path:
            self.drawio_path = Path(self.drawio_path)

    def validate_provider(self, provider: str) -> bool:
        """Check if a provider is properly configured"""
        if provider == 'siliconflow':
            return bool(self.siliconflow_api_key)
        elif provider == 'zhipu':
            return bool(self.zhipu_api_key)
        elif provider == 'custom':
            return bool(self.custom_api_key and self.custom_base_url)
        else:
            return False

    def get_provider_config(self, provider: str) -> dict:
        """Get configuration dict for a provider"""
        if provider == 'siliconflow':
            return {
                'api_key': self.siliconflow_api_key,
                'base_url': self.siliconflow_base_url,
                'model': self.siliconflow_model
            }
        elif provider == 'zhipu':
            return {
                'api_key': self.zhipu_api_key,
                'base_url': self.zhipu_base_url,
                'model': self.zhipu_model
            }
        elif provider == 'custom':
            return {
                'api_key': self.custom_api_key,
                'base_url': self.custom_base_url,
                'model': self.custom_model
            }
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def setup_logging(self):
        """Configure logging based on settings"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        handlers = [logging.StreamHandler()]

        if self.log_to_file:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.logs_dir / 'image-to-diagram.log'
            handlers.append(logging.FileHandler(log_file))

        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format=log_format,
            handlers=handlers,
            force=True
        )

        logger.info("Logging configured")

    @classmethod
    def from_env(cls) -> 'Settings':
        """Create settings from environment variables"""
        return cls()

    @classmethod
    def from_dict(cls, config: dict) -> 'Settings':
        """Create settings from dictionary"""
        return cls(**config)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance (lazy initialization)"""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
        _settings.setup_logging()
        logger.info("Settings initialized")
    return _settings


def update_settings(**kwargs):
    """Update global settings"""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()

    for key, value in kwargs.items():
        if hasattr(_settings, key):
            setattr(_settings, key, value)
        else:
            logger.warning(f"Unknown setting: {key}")

    logger.info(f"Settings updated: {kwargs}")
