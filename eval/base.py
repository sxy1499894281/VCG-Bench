"""
评估指标基类和注册器
提供灵活的指标系统，方便添加/删除指标
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """指标评估结果"""
    metric_name: str
    score: Optional[float]  # 主要分数（0-1），None表示API失败需要重新评估
    details: Dict[str, Any]  # 详细信息
    success: bool = True  # 是否成功计算
    error_message: Optional[str] = None  # 错误信息（如果有）


class BaseMetric(ABC):
    """评估指标基类"""
    
    def __init__(self, name: str, enabled: bool = True):
        """
        Args:
            name: 指标名称
            enabled: 是否启用该指标
        """
        self.name = name
        self.enabled = enabled
    
    @abstractmethod
    def evaluate(self, **kwargs) -> MetricResult:
        """
        评估指标
        
        Args:
            **kwargs: 指标所需的输入参数
        
        Returns:
            MetricResult: 评估结果
        """
        pass
    
    def __call__(self, **kwargs) -> MetricResult:
        """使指标可调用"""
        if not self.enabled:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"enabled": False},
                success=False,
                error_message="Metric is disabled"
            )
        
        try:
            return self.evaluate(**kwargs)
        except Exception as e:
            logger.error(f"Error evaluating metric {self.name}: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={},
                success=False,
                error_message=str(e)
            )


class MetricRegistry:
    """指标注册器 - 管理所有评估指标"""
    
    def __init__(self):
        self._metrics: Dict[str, BaseMetric] = {}
    
    def register(self, metric: BaseMetric):
        """注册指标"""
        self._metrics[metric.name] = metric
        logger.info(f"Registered metric: {metric.name}")
    
    def unregister(self, name: str):
        """取消注册指标"""
        if name in self._metrics:
            del self._metrics[name]
            logger.info(f"Unregistered metric: {name}")
    
    def get(self, name: str) -> Optional[BaseMetric]:
        """获取指标"""
        return self._metrics.get(name)
    
    def get_all(self) -> Dict[str, BaseMetric]:
        """获取所有指标"""
        return self._metrics.copy()
    
    def get_enabled(self) -> Dict[str, BaseMetric]:
        """获取所有启用的指标"""
        return {name: metric for name, metric in self._metrics.items() if metric.enabled}
    
    def enable(self, name: str):
        """启用指标"""
        if name in self._metrics:
            self._metrics[name].enabled = True
            logger.info(f"Enabled metric: {name}")
    
    def disable(self, name: str):
        """禁用指标"""
        if name in self._metrics:
            self._metrics[name].enabled = False
            logger.info(f"Disabled metric: {name}")
    
    def list_metrics(self) -> List[str]:
        """列出所有指标名称"""
        return list(self._metrics.keys())


# 全局指标注册器
_global_registry = MetricRegistry()


def get_registry() -> MetricRegistry:
    """获取全局指标注册器"""
    return _global_registry


def register_metric(metric: BaseMetric):
    """注册指标（便捷函数）"""
    _global_registry.register(metric)

