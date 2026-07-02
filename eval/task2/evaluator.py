"""
任务二评估运行器
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from eval.base import MetricRegistry, get_registry, MetricResult
from eval.task2.metrics import (
    ModifiedXMLExecutionSuccessRate,
    ModifiedXMLTokenCount,
    ModificationJSONTokenCount,
    StyleConsistencyScoreTask2,
    XDRFR,
    XMLEditDistance
)
from src.llm.client import LLMClient
from src.renderer.drawio_renderer import DrawioRenderer

logger = logging.getLogger(__name__)


def get_model_dir_name(model_name: str) -> str:
    """
    从模型名提取目录名
    对于带斜杠的模型名（如 zai-org/GLM-4.7），只取最后一个斜杠后的部分
    例如: zai-org/GLM-4.7 -> GLM-4.7
          Pro/deepseek-ai/DeepSeek-V3.2 -> DeepSeek-V3.2
          gemini-3-flash-preview -> gemini-3-flash-preview
    """
    if '/' in model_name:
        return model_name.split('/')[-1]
    return model_name


class Task2Evaluator:
    """任务二评估器"""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        renderer: Optional[DrawioRenderer] = None,
        enabled_metrics: Optional[List[str]] = None
    ):
        """
        Args:
            llm_client: LLM客户端
            renderer: 渲染器
            enabled_metrics: 启用的指标列表（None表示启用所有）
        """
        self.llm_client = llm_client or LLMClient()
        self.renderer = renderer or DrawioRenderer()
        self.registry = get_registry()
        
        # 注册所有指标
        self._register_metrics()
        
        # 设置启用的指标
        if enabled_metrics is not None:
            self._set_enabled_metrics(enabled_metrics)
    
    def _register_metrics(self):
        """注册所有指标"""
        self.registry.register(ModifiedXMLExecutionSuccessRate(renderer=self.renderer))
        self.registry.register(ModifiedXMLTokenCount())
        self.registry.register(ModificationJSONTokenCount())
        self.registry.register(StyleConsistencyScoreTask2(llm_client=self.llm_client))
        self.registry.register(XDRFR(llm_client=self.llm_client))
        self.registry.register(XMLEditDistance())
    
    def _set_enabled_metrics(self, enabled_metrics: List[str]):
        """设置启用的指标"""
        all_metrics = self.registry.list_metrics()
        for metric_name in all_metrics:
            if metric_name in enabled_metrics:
                self.registry.enable(metric_name)
            else:
                self.registry.disable(metric_name)
    
    def evaluate_sample_instruction(
        self,
        sample_dir: Path,
        instruction_id: str,
        model_name: str
    ) -> Dict[str, Any]:
        """
        评估单个样本的单个指令
        
        Args:
            sample_dir: 样本目录
            instruction_id: 指令ID（如 "inst_easy_001"）
            model_name: 模型名称
        
        Returns:
            评估结果字典
        """
        results = {
            "sample_id": sample_dir.name,
            "domain": sample_dir.parent.name,
            "instruction_id": instruction_id,
            "model": model_name,
            "metrics": {}
        }
        
        instruction_dir = sample_dir / "instructions" / instruction_id
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = instruction_dir / f"model_{model_dir_name}"
        
        # 准备输入路径
        original_rendered_path = sample_dir / "rendered.png"
        instruction_path = instruction_dir / "instruction.txt"
        modified_xml_path = model_dir / "modified.xml"
        modified_rendered_path = model_dir / "modified.png"
        original_xml_path = sample_dir / "diagram.xml"
        model_output_json_path = model_dir / "model_output.json"
        
        # 检查渲染文件是否存在（如果不存在，返回0分）
        if not modified_rendered_path.exists():
            logger.error(f"Rendered image not found: {modified_rendered_path}")
            logger.error(f"Please run batch_render.py first")
            
            # 返回失败结果（所有指标为0）
            enabled_metrics = self.registry.get_enabled()
            return {
                "sample_id": sample_dir.name,
                "domain": sample_dir.parent.name,
                "instruction_id": instruction_id,
                "model": model_name,
                "metrics": {
                    metric_name: {
                        "score": 0.0,
                        "success": False,
                        "details": {"error": "Image not found"}
                    }
                    for metric_name in enabled_metrics.keys()
                },
                "error": "Rendered image not found. Please run batch_render.py first."
            }
        
        # 检查执行是否成功
        execution_success = modified_rendered_path.exists()
        
        # 读取指令文本
        instruction_text = ""
        if instruction_path.exists():
            instruction_text = instruction_path.read_text(encoding='utf-8').strip()
        
        # 读取问题集合（用于 XDRFR，只包含拆解问题，不再包含共用问题）
        decomposed_questions = []
        question_set_path = instruction_dir / "question_set.json"
        if question_set_path.exists():
            try:
                with open(question_set_path, 'r', encoding='utf-8') as f:
                    question_set_data = json.load(f)
                    decomposed_questions = question_set_data.get("decomposed_questions", [])
            except Exception as e:
                logger.warning(f"Failed to load question set from {question_set_path}: {e}")
        
        # 读取原始XML和修改后的XML（用于XDRFR）
        original_xml = ""
        modified_xml = ""
        if original_xml_path.exists():
            original_xml = original_xml_path.read_text(encoding='utf-8')
        if modified_xml_path.exists():
            modified_xml = modified_xml_path.read_text(encoding='utf-8')
        
        # 读取指令难度（如果有）
        try:
            instruction_metadata_path = instruction_dir / "instruction_metadata.json"
            if instruction_metadata_path.exists():
                instruction_metadata = json.loads(instruction_metadata_path.read_text())
                results["instruction_level"] = instruction_metadata.get("difficulty_level", "unknown")
            else:
                # 如果 metadata 文件不存在，尝试从 instruction_id 中提取难度信息
                # instruction_id 格式通常是 "inst_easy_001", "inst_medium_002", "inst_hard_003" 等
                if instruction_id.startswith("inst_"):
                    parts = instruction_id.split("_")
                    if len(parts) >= 2:
                        difficulty = parts[1].capitalize()  # easy -> Easy, medium -> Medium, hard -> Hard
                        results["instruction_level"] = difficulty
                    else:
                        results["instruction_level"] = "unknown"
                else:
                    results["instruction_level"] = "unknown"
        except Exception as e:
            logger.warning(f"Failed to read instruction level for {instruction_id}: {e}")
            # 如果读取失败，尝试从 instruction_id 中提取
            if instruction_id.startswith("inst_"):
                parts = instruction_id.split("_")
                if len(parts) >= 2:
                    difficulty = parts[1].capitalize()
                    results["instruction_level"] = difficulty
                else:
                    results["instruction_level"] = "unknown"
            else:
                results["instruction_level"] = "unknown"
        
        # 执行所有启用的指标
        enabled_metrics = self.registry.get_enabled()
        
        for metric_name, metric in enabled_metrics.items():
            try:
                if metric_name == "modified_xml_execution_success_rate":
                    result = metric(
                        modified_xml_path=modified_xml_path,
                        modified_rendered_path=modified_rendered_path
                    )
                    # 更新 execution_success 状态
                    if result.success:
                        execution_success = result.details.get("execution_success", execution_success)
                elif metric_name == "modified_xml_token_count":
                    result = metric(modified_xml_path=modified_xml_path)
                elif metric_name == "modification_json_token_count":
                    if model_output_json_path.exists():
                        result = metric(model_output_json_path=model_output_json_path)
                    else:
                        logger.warning(f"Model output JSON not found for {sample_dir.name}/{instruction_id}, skipping MJTC")
                        result = MetricResult(
                            metric_name=metric_name,
                            score=None,
                            details={"error": "Model output JSON not found"},
                            success=False,
                            error_message="Model output JSON not found"
                        )
                elif metric_name == "style_consistency_score_task2":
                    result = metric(
                        gemini_rendered_path=original_rendered_path,
                        modified_rendered_path=modified_rendered_path,
                        execution_success=execution_success
                    )
                elif metric_name == "xdrfr":
                    if decomposed_questions and model_output_json_path.exists():
                        # Read model output JSON (only use model_output_json, not original XML, to save costs)
                        try:
                            with open(model_output_json_path, 'r', encoding='utf-8') as f:
                                model_output_json = json.load(f)
                        except Exception as e:
                            logger.warning(f"Failed to load model output JSON from {model_output_json_path}: {e}, skipping XDRFR")
                            result = MetricResult(
                                metric_name=metric_name,
                                score=None,
                                details={"error": f"Failed to load model output JSON: {e}"},
                                success=False,
                                error_message=f"Failed to load model output JSON: {e}"
                            )
                            results["metrics"][metric_name] = {
                                "score": result.score,
                                "success": result.success,
                                "details": result.details
                            }
                            continue
                        
                        if not model_output_json:
                            logger.warning(f"Model output JSON is empty for {sample_dir.name}/{instruction_id}, skipping XDRFR")
                            result = MetricResult(
                                metric_name=metric_name,
                                score=None,
                                details={"error": "Model output JSON is empty"},
                                success=False,
                                error_message="Model output JSON is empty"
                            )
                            results["metrics"][metric_name] = {
                                "score": result.score,
                                "success": result.success,
                                "details": result.details
                            }
                            continue
                        
                        result = metric(
                            model_output_json=model_output_json,
                            instruction=instruction_text,
                            decomposed_questions=decomposed_questions,
                            execution_success=execution_success
                        )
                    else:
                        logger.warning(f"Question set or model output JSON not found for {sample_dir.name}/{instruction_id}, skipping XDRFR")
                        result = MetricResult(
                            metric_name=metric_name,
                            score=None,
                            details={"error": "Question set or model output JSON not found"},
                            success=False,
                            error_message="Question set or model output JSON not found"
                        )
                elif metric_name == "xml_edit_distance":
                    result = metric(
                        gemini_xml_path=original_xml_path,
                        modified_xml_path=modified_xml_path
                    )
                else:
                    continue
                
                results["metrics"][metric_name] = {
                    "score": result.score,
                    "success": result.success,
                    "details": result.details
                }
            except Exception as e:
                error_str = str(e).lower()
                # 检测 524 错误，保存为 success=False，避免无限制重试和重复计费
                if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                    logger.error(f"HTTP 524 Cloudflare timeout error when evaluating {metric_name} for {sample_dir}/{instruction_id}: {e}")
                    logger.error("Saving result as success=False. Will retry on next run, but please check API server status first.")
                    results["metrics"][metric_name] = {
                        "score": None,
                        "success": False,
                        "details": {
                            "error": str(e),
                            "error_type": "524_timeout",
                            "message": "HTTP 524 Cloudflare timeout - server may still be processing request"
                        },
                        "error_message": f"HTTP 524 Cloudflare timeout: {e}"
                    }
                else:
                    logger.error(f"Error evaluating {metric_name} for {sample_dir}/{instruction_id}: {e}")
                    # 其他错误保存为None，后面重新运行再更新
                    results["metrics"][metric_name] = None
        
        return results
    
    def evaluate_all(
        self,
        benchmark_dir: Path,
        output_dir: Path,
        models: Optional[List[str]] = None,
        domain_filter: Optional[List[str]] = None
    ):
        """
        评估所有样本和指令（支持增量评估）
        
        Args:
            benchmark_dir: task2_benchmark目录
            output_dir: 输出目录
            models: 要评估的模型列表（None表示评估所有模型）
            domain_filter: 要评估的领域列表（None表示评估所有领域，如 ['domain_academic_domain_architecture', 'domain_business_domain_product']）
        """
        # 确保路径是Path对象
        benchmark_dir = Path(benchmark_dir)
        output_dir = Path(output_dir)
        
        # 检查benchmark目录是否存在
        if not benchmark_dir.exists():
            logger.error(
                f"Benchmark directory does not exist: {benchmark_dir}\n"
                f"  Current working directory: {Path.cwd()}"
            )
            raise ValueError(f"Benchmark directory does not exist: {benchmark_dir}")
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建分片文件目录
        fragments_dir = output_dir / "fragments"
        fragments_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Benchmark directory: {benchmark_dir}")
        logger.info(f"Output directory: {output_dir}")
        
        # 加载已有结果（从分片文件中加载）
        existing_results = self._load_existing_results(output_dir)
        
        all_results = []
        
        # 确定要处理的领域
        if domain_filter:
            # 只处理指定的领域
            domain_dirs = []
            for domain_name in domain_filter:
                # 支持两种格式：带 domain_ 前缀或不带
                if not domain_name.startswith("domain_"):
                    domain_name = f"domain_{domain_name}"
                domain_path = benchmark_dir / domain_name
                if domain_path.exists() and domain_path.is_dir():
                    domain_dirs.append(domain_path)
                else:
                    logger.warning(f"Domain '{domain_name}' not found, skipping")
            domain_dirs = sorted(domain_dirs)
        else:
            # 处理所有领域
            domain_dirs = sorted(benchmark_dir.glob("domain_*"))
        
        logger.info(f"Processing {len(domain_dirs)} domains: {[d.name for d in domain_dirs]}")
        
        # 统计总样本数（用于显示进度）
        total_samples = 0
        total_instructions = 0
        for domain_dir in domain_dirs:
            for sample_dir in sorted(domain_dir.glob("sample_*")):
                instructions_dir = sample_dir / "instructions"
                if instructions_dir.exists():
                    total_samples += 1
                    total_instructions += len(list(instructions_dir.glob("inst_*")))
        logger.info(f"Total samples to process: {total_samples}, Total instructions: {total_instructions}")
        
        current_sample_index = 0
        current_instruction_index = 0
        
        # 遍历所有domain
        for domain_index, domain_dir in enumerate(domain_dirs, 1):
            domain = domain_dir.name
            sample_dirs = sorted(domain_dir.glob("sample_*"))
            domain_instructions = 0
            for sample_dir in sample_dirs:
                instructions_dir = sample_dir / "instructions"
                if instructions_dir.exists():
                    domain_instructions += len(list(instructions_dir.glob("inst_*")))
            logger.info(f"[{domain_index}/{len(domain_dirs)}] Processing domain: {domain} ({len(sample_dirs)} samples, {domain_instructions} instructions)")
            
            # 遍历所有样本
            for sample_index, sample_dir in enumerate(sample_dirs, 1):
                sample_id = sample_dir.name
                current_sample_index += 1
                logger.info(f"[{domain_index}/{len(domain_dirs)}] [{sample_index}/{len(sample_dirs)}] [{current_sample_index}/{total_samples}] Processing sample: {domain}/{sample_id}")
                
                instructions_dir = sample_dir / "instructions"
                if not instructions_dir.exists():
                    logger.warning(f"[{domain}/{sample_id}] No instructions directory found: {instructions_dir}")
                    continue
                
                instruction_dirs = sorted(instructions_dir.glob("inst_*"))
                # 遍历所有指令
                for instruction_index, instruction_dir in enumerate(instruction_dirs, 1):
                    instruction_id = instruction_dir.name
                    current_instruction_index += 1
                    logger.info(f"[{domain}/{sample_id}] [{instruction_index}/{len(instruction_dirs)}] Processing instruction: {instruction_id}")
                    
                    # 确定要评估的模型
                    if models is None:
                        model_dirs = list(instruction_dir.glob("model_*"))
                        model_names = [d.name.replace("model_", "") for d in model_dirs]
                    else:
                        model_names = models
                    
                    # 评估每个模型
                    for model_name in model_names:
                        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
                        model_dir_name = get_model_dir_name(model_name)
                        model_dir = instruction_dir / f"model_{model_dir_name}"
                        if not model_dir.exists():
                            logger.warning(f"Model directory not found: {model_dir} (absolute: {model_dir.resolve()})")
                            continue
                        logger.debug(f"Found model directory: {model_dir}")
                        
                        # 检查是否已有结果
                        sample_key = f"{domain}/{sample_id}/{instruction_id}/{model_name}"
                        existing_result_obj = existing_results.get(sample_key, {})
                        # existing_result_obj 是完整的结果对象，提取 metrics
                        existing_metrics = existing_result_obj.get("metrics", {}) if isinstance(existing_result_obj, dict) else {}

                        # ========================================
                        # 第一步：数据一致性检查（优先级最高）
                        # 检查是否存在数据错乱，如果有则清空所有metrics
                        # ========================================
                        data_corrupted = False

                        # 尝试从多个metric中检查路径（优先级从高到低）
                        # 1. modified_xml_execution_success_rate（总是存在）
                        # 2. modified_xml_token_count（只要modified.xml存在就会评估）
                        # 3. xml_edit_distance（总是存在，因为需要比较原始XML和修改后XML）
                        # 4. style_consistency_score_task2（需要PNG渲染成功才有）

                        check_path = None
                        check_metric_name = None

                        # 优先检查modified_xml_execution_success_rate
                        if 'modified_xml_execution_success_rate' in existing_metrics:
                            existing_mesr = existing_metrics['modified_xml_execution_success_rate']
                            if isinstance(existing_mesr, dict) and existing_mesr.get('details'):
                                details = existing_mesr['details']
                                check_path = details.get('modified_xml_path') or details.get('modified_rendered_path')
                                if check_path:
                                    check_metric_name = 'modified_xml_execution_success_rate'

                        # 如果没有modified_xml_execution_success_rate，检查modified_xml_token_count
                        if not check_path and 'modified_xml_token_count' in existing_metrics:
                            existing_mxtc = existing_metrics['modified_xml_token_count']
                            if isinstance(existing_mxtc, dict) and existing_mxtc.get('details'):
                                details = existing_mxtc['details']
                                check_path = details.get('modified_xml_path')
                                if check_path:
                                    check_metric_name = 'modified_xml_token_count'

                        # 如果没有modified_xml_token_count，检查xml_edit_distance
                        if not check_path and 'xml_edit_distance' in existing_metrics:
                            existing_xed = existing_metrics['xml_edit_distance']
                            if isinstance(existing_xed, dict) and existing_xed.get('details'):
                                details = existing_xed['details']
                                check_path = details.get('modified_xml_path') or details.get('gemini_xml_path')
                                if check_path:
                                    check_metric_name = 'xml_edit_distance'

                        # 如果没有xml_edit_distance，检查style_consistency_score_task2
                        if not check_path and 'style_consistency_score_task2' in existing_metrics:
                            existing_scs = existing_metrics['style_consistency_score_task2']
                            if isinstance(existing_scs, dict) and existing_scs.get('details'):
                                details = existing_scs['details']
                                check_path = details.get('modified_rendered_path') or details.get('gemini_rendered_path')
                                if check_path:
                                    check_metric_name = 'style_consistency_score_task2'

                        # 如果有路径可以检查，进行数据一致性验证
                        if check_path and 'domain_' in check_path and 'sample_' in check_path and 'inst_' in check_path:
                            # 从路径中提取domain、sample_id和instruction_id
                            path_parts = check_path.split('/')
                            path_domain = None
                            path_sample_id = None
                            path_instruction_id = None
                            for part in path_parts:
                                if part.startswith('domain_'):
                                    path_domain = part
                                elif part.startswith('sample_'):
                                    path_sample_id = part
                                elif part.startswith('inst_'):
                                    path_instruction_id = part

                            # 检查domain、sample_id和instruction_id是否都匹配
                            if path_domain and path_sample_id and path_instruction_id:
                                if path_domain != domain or path_sample_id != sample_id or path_instruction_id != instruction_id:
                                    # 检测到数据错乱
                                    logger.warning(
                                        f"[{domain}/{sample_id}/{instruction_id}] ⚠️  DATA CORRUPTION DETECTED! "
                                        f"Metric '{check_metric_name}' contains wrong path. "
                                        f"Expected: {domain}/{sample_id}/{instruction_id}, "
                                        f"Found in path: {path_domain}/{path_sample_id}/{path_instruction_id}. "
                                        f"This means all metrics are from the wrong sample/instruction!"
                                    )
                                    logger.warning(
                                        f"[{domain}/{sample_id}/{instruction_id}] 🔄 AUTOMATIC FIX: Clearing all corrupted metrics and re-evaluating from scratch."
                                    )
                                    corrupted_metrics = list(existing_metrics.keys())
                                    existing_metrics.clear()
                                    logger.info(f"[{domain}/{sample_id}/{instruction_id}] Cleared {len(corrupted_metrics)} corrupted metrics: {corrupted_metrics}")
                                    data_corrupted = True

                        # ========================================
                        # 第二步：检查是否所有启用的指标都已评估且成功
                        # 只有在数据一致性检查通过后才进行
                        # ========================================
                        enabled_metrics = self.registry.get_enabled()
                        all_metrics_evaluated = True
                        for metric_name in enabled_metrics.keys():
                            if metric_name not in existing_metrics or existing_metrics[metric_name] is None:
                                logger.info(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' not found or None for {sample_id}/{instruction_id}/{model_name}, will evaluate")
                                all_metrics_evaluated = False
                                break
                            # 检查结果是否有效（必须成功且有有效的分数）
                            existing_metric_result = existing_metrics[metric_name]
                            if not (isinstance(existing_metric_result, dict) and existing_metric_result.get("score") is not None):
                                logger.info(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' invalid (not dict or score is None) for {sample_id}/{instruction_id}/{model_name}, will evaluate")
                                all_metrics_evaluated = False
                                break
                            # 检查是否成功（如果 success=False，需要重试）
                            # 处理 success 可能是布尔值、字符串或缺失的情况
                            success_value = existing_metric_result.get("success")
                            if success_value is None:
                                # 如果 success 字段不存在，默认认为成功（向后兼容）
                                success_value = True
                            elif isinstance(success_value, str):
                                # 如果是字符串，转换为布尔值
                                success_value = success_value.lower() in ('true', '1', 'yes')
                            elif not isinstance(success_value, bool):
                                # 如果是其他类型，尝试转换为布尔值
                                success_value = bool(success_value)

                            if not success_value:
                                logger.warning(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' for {sample_id}/{instruction_id}/{model_name} failed previously (success={existing_metric_result.get('success')}), will retry")
                                all_metrics_evaluated = False
                                break
                            else:
                                logger.debug(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' for {sample_id}/{instruction_id}/{model_name} is valid (success={success_value}, score={existing_metric_result.get('score')})")

                        if all_metrics_evaluated:
                            # 所有指标都已评估，直接跳过该样本
                            logger.info(f"[{domain}/{sample_id}/{instruction_id}] Sample {sample_id}/{instruction_id}/{model_name} already fully evaluated, skipping")
                            # 从已有结果中构建结果字典（用于后续CSV生成）
                            result = {
                                "sample_id": sample_id,
                                "domain": domain,
                                "instruction_id": instruction_id,
                                "model": model_name,
                                "metrics": existing_metrics,
                                "instruction_level": existing_result_obj.get("instruction_level", "unknown") if isinstance(existing_result_obj, dict) else "unknown"
                            }
                            all_results.append(result)
                            
                            # 检查分片文件是否存在，如果不存在则保存（即使跳过了评估）
                            # 这样可以确保从 detailed_results.json 加载的数据也会被保存到分片文件
                            safe_model_name = model_name.replace("/", "_").replace("\\", "_")
                            safe_domain = domain.replace("/", "_").replace("\\", "_")
                            fragment_file = output_dir / "fragments" / f"{safe_model_name}_{safe_domain}_results.json"
                            if not fragment_file.exists():
                                logger.info(f"[{domain}/{sample_id}/{instruction_id}] Fragment file not found, saving skipped sample to fragment file")
                                self._save_single_result(result, output_dir, model_name, domain)
                            continue
                        
                        # 增量评估：只评估缺失的指标
                        logger.info(f"[{domain}/{sample_id}/{instruction_id}] Evaluating {sample_id}/{instruction_id} - {model_name}")
                        try:
                            result = self.evaluate_sample_instruction_incremental(
                                sample_dir, 
                                instruction_id, 
                                model_name,
                                existing_metrics
                            )
                            all_results.append(result)
                            
                            # 实时保存：每个样本评估完成后立即保存到分片文件（按模型-领域分组）
                            self._save_single_result(result, output_dir, model_name, domain)
                            logger.info(f"[{domain}/{sample_id}/{instruction_id}] Saved result for {sample_id}/{instruction_id}/{model_name} to fragment file")
                        except Exception as e:
                            logger.error(f"[{domain}/{sample_id}/{instruction_id}] Error evaluating {sample_id}/{instruction_id}/{model_name}: {e}", exc_info=True)
                            # 即使出错也继续处理下一个样本
                            continue
        
        # 最后批量保存CSV结果（重新生成所有CSV文件，确保包含所有结果）
        logger.info("Generating CSV files from all saved results...")
        self._regenerate_csv_results(output_dir)
        
        logger.info(f"Evaluation completed. Results saved to {output_dir}")
    
    def _load_existing_results(self, output_dir: Path, model: Optional[str] = None, domain: Optional[str] = None) -> Dict[str, Dict]:
        """
        加载已有结果（从分片文件中加载）
        
        Args:
            output_dir: 输出目录
            model: 模型名称（可选，用于过滤）
            domain: 领域名称（可选，用于过滤）
        
        Returns:
            {sample_key: result_obj} 格式的字典
        """
        fragments_dir = output_dir / "fragments"
        existing = {}
        
        # 从分片文件加载
        if fragments_dir.exists():
            # 构建文件名模式
            if model and domain:
                # 加载特定的模型-领域分片
                fragment_file = fragments_dir / f"{model}_{domain}_results.json"
                fragment_files = [fragment_file] if fragment_file.exists() else []
            elif model:
                # 加载特定模型的所有领域分片
                pattern = f"{model}_*_results.json"
                fragment_files = list(fragments_dir.glob(pattern))
            elif domain:
                # 加载特定领域的所有模型分片
                pattern = f"*_{domain}_results.json"
                fragment_files = list(fragments_dir.glob(pattern))
            else:
                # 加载所有分片文件
                fragment_files = list(fragments_dir.glob("*_results.json"))
            
            for fragment_file in fragment_files:
                try:
                    with open(fragment_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 处理不同的数据格式
                    instructions = []
                    if isinstance(data, dict):
                        instructions = data.get("instructions", [])
                    elif isinstance(data, list):
                        instructions = data
                    else:
                        logger.warning(f"Unexpected data format in {fragment_file}, expected dict or list")
                        continue
                    
                    # 添加到已有结果中
                    for result in instructions:
                        if not isinstance(result, dict):
                            continue
                        
                        sample_id = result.get("sample_id", "")
                        instruction_id = result.get("instruction_id", "")
                        model_name = result.get("model", "")
                        domain_name = result.get("domain", "")
                        if not sample_id or not instruction_id or not model_name:
                            continue

                        sample_key = f"{domain_name}/{sample_id}/{instruction_id}/{model_name}"
                        # 如果已有结果，合并指标（保留已有指标，更新新指标）
                        if sample_key in existing:
                            existing_result = existing[sample_key]
                            existing_metrics = existing_result.get("metrics", {})
                            new_metrics = result.get("metrics", {})
                            for metric_name, metric_value in new_metrics.items():
                                existing_metrics[metric_name] = metric_value
                            existing_result["metrics"] = existing_metrics
                            # 更新其他字段
                            if "instruction_level" in result:
                                existing_result["instruction_level"] = result["instruction_level"]
                            if "domain" in result:
                                existing_result["domain"] = result["domain"]
                        else:
                            existing[sample_key] = result
                except Exception as e:
                    logger.warning(f"Failed to load fragment file {fragment_file}: {e}")
                    continue
        
        # 只从分片文件加载，不从 detailed_results.json 加载
        # 没有分片文件就说明需要运行
        fragments_count = len([f for f in fragments_dir.glob("*_results.json")] if fragments_dir.exists() else [])
        logger.info(f"Loaded {len(existing)} existing results from {fragments_count} fragment files")
        return existing
    
    def evaluate_sample_instruction_incremental(
        self,
        sample_dir: Path,
        instruction_id: str,
        model_name: str,
        existing_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        增量评估单个样本的单个指令，只评估缺失的指标
        
        Args:
            sample_dir: 样本目录
            instruction_id: 指令ID
            model_name: 模型名称
            existing_metrics: 已有指标结果
        
        Returns:
            评估结果字典
        """
        results = {
            "sample_id": sample_dir.name,
            "domain": sample_dir.parent.name,
            "instruction_id": instruction_id,
            "model": model_name,
            "metrics": {}
        }
        
        # 获取启用的指标
        enabled_metrics = self.registry.get_enabled()
        
        # 确定需要评估的指标
        domain = sample_dir.parent.name
        sample_id = sample_dir.name
        metrics_to_evaluate = []
        for metric_name, metric in enabled_metrics.items():
            # 检查是否已有结果
            if metric_name in existing_metrics and existing_metrics[metric_name] is not None:
                # 检查结果是否有效（有 score 字段且不为 None）
                existing_result = existing_metrics[metric_name]
                if isinstance(existing_result, dict) and existing_result.get("score") is not None:
                    # 检查是否成功（如果 success=False，需要重新评估）
                    if not existing_result.get("success", True):
                        logger.info(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' failed previously (success=False), will re-evaluate")
                        metrics_to_evaluate.append((metric_name, metric))
                    else:
                        logger.info(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' already evaluated, reusing result")
                        results["metrics"][metric_name] = existing_result
                    continue
            
            logger.info(f"[{domain}/{sample_id}/{instruction_id}] Metric '{metric_name}' not found or invalid, will evaluate")
            metrics_to_evaluate.append((metric_name, metric))
        
        # 准备输入路径（与 evaluate_sample_instruction 相同）
        instruction_dir = sample_dir / "instructions" / instruction_id
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = instruction_dir / f"model_{model_dir_name}"
        
        # 读取指令难度（必须在提前返回之前执行，确保即使所有指标都已评估，instruction_level 也会被设置）
        try:
            instruction_metadata_path = instruction_dir / "instruction_metadata.json"
            if instruction_metadata_path.exists():
                instruction_metadata = json.loads(instruction_metadata_path.read_text())
                results["instruction_level"] = instruction_metadata.get("difficulty_level", "unknown")
            else:
                # 如果 metadata 文件不存在，尝试从 instruction_id 中提取难度信息
                # instruction_id 格式通常是 "inst_easy_001", "inst_medium_002", "inst_hard_003" 等
                if instruction_id.startswith("inst_"):
                    parts = instruction_id.split("_")
                    if len(parts) >= 2:
                        difficulty = parts[1].capitalize()  # easy -> Easy, medium -> Medium, hard -> Hard
                        results["instruction_level"] = difficulty
                    else:
                        results["instruction_level"] = "unknown"
                else:
                    results["instruction_level"] = "unknown"
        except Exception as e:
            logger.warning(f"[{domain}/{sample_id}/{instruction_id}] Failed to read instruction level for {instruction_id}: {e}")
            # 如果读取失败，尝试从 instruction_id 中提取
            if instruction_id.startswith("inst_"):
                parts = instruction_id.split("_")
                if len(parts) >= 2:
                    difficulty = parts[1].capitalize()
                    results["instruction_level"] = difficulty
                else:
                    results["instruction_level"] = "unknown"
            else:
                results["instruction_level"] = "unknown"
        
        # 评估缺失的指标
        if not metrics_to_evaluate:
            logger.info(f"[{domain}/{sample_id}/{instruction_id}] All metrics already evaluated for {sample_id}/{instruction_id}/{model_name}")
            return results
        
        logger.info(f"[{domain}/{sample_id}/{instruction_id}] Evaluating {len(metrics_to_evaluate)} metrics for {sample_id}/{instruction_id}/{model_name}")
        
        original_rendered_path = sample_dir / "rendered.png"
        instruction_path = instruction_dir / "instruction.txt"
        modified_xml_path = model_dir / "modified.xml"
        modified_rendered_path = model_dir / "modified.png"
        original_xml_path = sample_dir / "diagram.xml"
        model_output_json_path = model_dir / "model_output.json"
        
        # 检查执行是否成功
        execution_success = modified_rendered_path.exists()
        
        # 读取指令文本
        instruction_text = ""
        if instruction_path.exists():
            instruction_text = instruction_path.read_text(encoding='utf-8').strip()
        
        # 读取问题集合（用于 XDRFR，只包含拆解问题，不再包含共用问题）
        decomposed_questions = []
        question_set_path = instruction_dir / "question_set.json"
        if question_set_path.exists():
            try:
                with open(question_set_path, 'r', encoding='utf-8') as f:
                    question_set_data = json.load(f)
                    decomposed_questions = question_set_data.get("decomposed_questions", [])
            except Exception as e:
                logger.warning(f"[{domain}/{sample_id}/{instruction_id}] Failed to load question set from {question_set_path}: {e}")
        
        # 读取原始XML和修改后的XML（用于XDRFR）
        original_xml = ""
        modified_xml = ""
        if original_xml_path.exists():
            original_xml = original_xml_path.read_text(encoding='utf-8')
        if modified_xml_path.exists():
            modified_xml = modified_xml_path.read_text(encoding='utf-8')
        
        # 评估缺失的指标
        for metric_index, (metric_name, metric) in enumerate(metrics_to_evaluate, 1):
            logger.info(f"[{domain}/{sample_id}/{instruction_id}] [{metric_index}/{len(metrics_to_evaluate)}] Evaluating metric: {metric_name}")
            try:
                if metric_name == "modified_xml_execution_success_rate":
                    result = metric(
                        modified_xml_path=modified_xml_path,
                        modified_rendered_path=modified_rendered_path
                    )
                    if result.success:
                        execution_success = result.details.get("execution_success", execution_success)
                elif metric_name == "modified_xml_token_count":
                    result = metric(modified_xml_path=modified_xml_path)
                elif metric_name == "modification_json_token_count":
                    if model_output_json_path.exists():
                        result = metric(model_output_json_path=model_output_json_path)
                    else:
                        logger.warning(f"Model output JSON not found for {sample_dir.name}/{instruction_id}, skipping MJTC")
                        result = MetricResult(
                            metric_name=metric_name,
                            score=None,
                            details={"error": "Model output JSON not found"},
                            success=False,
                            error_message="Model output JSON not found"
                        )
                elif metric_name == "style_consistency_score_task2":
                    result = metric(
                        gemini_rendered_path=original_rendered_path,
                        modified_rendered_path=modified_rendered_path,
                        execution_success=execution_success
                    )
                elif metric_name == "xdrfr":
                    if decomposed_questions and model_output_json_path.exists():
                        # Read model output JSON (only use model_output_json, not original XML, to save costs)
                        try:
                            with open(model_output_json_path, 'r', encoding='utf-8') as f:
                                model_output_json = json.load(f)
                        except Exception as e:
                            logger.warning(f"Failed to load model output JSON from {model_output_json_path}: {e}, skipping XDRFR")
                            result = MetricResult(
                                metric_name=metric_name,
                                score=None,
                                details={"error": f"Failed to load model output JSON: {e}"},
                                success=False,
                                error_message=f"Failed to load model output JSON: {e}"
                            )
                            results["metrics"][metric_name] = {
                                "score": result.score,
                                "success": result.success,
                                "details": result.details
                            }
                            continue
                        
                        if not model_output_json:
                            logger.warning(f"Model output JSON is empty for {sample_dir.name}/{instruction_id}, skipping XDRFR")
                            result = MetricResult(
                                metric_name=metric_name,
                                score=None,
                                details={"error": "Model output JSON is empty"},
                                success=False,
                                error_message="Model output JSON is empty"
                            )
                            results["metrics"][metric_name] = {
                                "score": result.score,
                                "success": result.success,
                                "details": result.details
                            }
                            continue
                        
                        result = metric(
                            model_output_json=model_output_json,
                            instruction=instruction_text,
                            decomposed_questions=decomposed_questions,
                            execution_success=execution_success
                        )
                    else:
                        logger.warning(f"Question set or model output JSON not found for {sample_dir.name}/{instruction_id}, skipping XDRFR")
                        result = MetricResult(
                            metric_name=metric_name,
                            score=None,
                            details={"error": "Question set or model output JSON not found"},
                            success=False,
                            error_message="Question set or model output JSON not found"
                        )
                elif metric_name == "xml_edit_distance":
                    result = metric(
                        gemini_xml_path=original_xml_path,
                        modified_xml_path=modified_xml_path
                    )
                else:
                    continue
                
                results["metrics"][metric_name] = {
                    "score": result.score,
                    "success": result.success,
                    "details": result.details
                }
            except Exception as e:
                error_str = str(e).lower()
                # 检测 524 错误，保存为 success=False，避免无限制重试和重复计费
                if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                    logger.error(f"HTTP 524 Cloudflare timeout error when evaluating {metric_name} for {sample_dir}/{instruction_id}: {e}")
                    logger.error("Saving result as success=False. Will retry on next run, but please check API server status first.")
                    results["metrics"][metric_name] = {
                        "score": None,
                        "success": False,
                        "details": {
                            "error": str(e),
                            "error_type": "524_timeout",
                            "message": "HTTP 524 Cloudflare timeout - server may still be processing request"
                        },
                        "error_message": f"HTTP 524 Cloudflare timeout: {e}"
                    }
                else:
                    logger.error(f"Error evaluating {metric_name} for {sample_dir}/{instruction_id}: {e}")
                    # 其他错误保存为None，后面重新运行再更新
                    results["metrics"][metric_name] = None
        
        return results
    
    def _save_single_result(
        self,
        result: Dict[str, Any],
        output_dir: Path,
        model_name: str,
        domain: str
    ):
        """
        实时保存单个样本指令的评估结果到分片文件（按模型-领域分组，避免并发写入竞争）
        
        Args:
            result: 单个样本指令的评估结果
            output_dir: 输出目录
            model_name: 模型名称
            domain: 领域名称
        """
        fragments_dir = output_dir / "fragments"
        fragments_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建分片文件名：{model}_{domain}_results.json
        # 清理模型名和领域名中的特殊字符（用于文件名）
        safe_model_name = model_name.replace("/", "_").replace("\\", "_")
        safe_domain = domain.replace("/", "_").replace("\\", "_")
        fragment_file = fragments_dir / f"{safe_model_name}_{safe_domain}_results.json"
        
        # 原子写入分片文件（不需要文件锁，因为每个进程只写自己的文件）
        temp_path = fragment_file.with_suffix('.tmp')
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                # 加载已有结果（该模型-领域的分片文件）
                all_results = []
                if fragment_file.exists():
                    try:
                        with open(fragment_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            all_results = data.get("instructions", [])
                        elif isinstance(data, list):
                            all_results = data
                    except Exception as e:
                        logger.warning(f"Failed to load existing fragment file {fragment_file}: {e}, starting fresh")
                        all_results = []
                
                # 查找是否已有该样本指令的结果
                sample_key = f"{result.get('domain', '')}/{result['sample_id']}/{result['instruction_id']}/{result['model']}"
                found = False
                for i, existing_result in enumerate(all_results):
                    existing_key = f"{existing_result.get('domain', '')}/{existing_result.get('sample_id')}/{existing_result.get('instruction_id')}/{existing_result.get('model')}"
                    if existing_key == sample_key:
                        # 更新已有结果：合并指标（保留已有指标，只更新/添加新指标）
                        existing_metrics = existing_result.get("metrics", {})
                        new_metrics = result.get("metrics", {})
                        for metric_name, metric_value in new_metrics.items():
                            existing_metrics[metric_name] = metric_value
                        all_results[i]["metrics"] = existing_metrics
                        # 更新其他字段（如 instruction_level, domain）
                        if "instruction_level" in result:
                            all_results[i]["instruction_level"] = result["instruction_level"]
                        if "domain" in result:
                            all_results[i]["domain"] = result["domain"]
                        found = True
                        break
                
                # 如果没找到，添加新结果
                if not found:
                    all_results.append(result)
                
                # 写入临时文件
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump({"instructions": all_results}, f, indent=2, ensure_ascii=False)
                
                # 原子替换
                temp_path.replace(fragment_file)
                
                logger.debug(f"Saved result to fragment file: {fragment_file}")
                break  # 成功，退出重试循环
                
            except (IOError, OSError, json.JSONEncodeError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to save result to fragment (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))  # 指数退避
                    # 清理临时文件（如果存在）
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except:
                            pass
                else:
                    logger.error(f"Failed to save result to fragment after {max_retries} attempts: {e}", exc_info=True)
                    # 清理临时文件
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except:
                            pass
                    raise
    
    def _merge_fragment_files(self, output_dir: Path) -> List[Dict[str, Any]]:
        """
        合并所有分片文件，生成完整的结果列表
        
        Args:
            output_dir: 输出目录
        
        Returns:
            合并后的所有结果列表
        """
        fragments_dir = output_dir / "fragments"
        all_results = []
        seen_keys = set()
        
        if not fragments_dir.exists():
            logger.warning(f"Fragments directory not found: {fragments_dir}")
            return all_results
        
        # 加载所有分片文件
        fragment_files = list(fragments_dir.glob("*_results.json"))
        logger.info(f"Merging {len(fragment_files)} fragment files...")
        
        for fragment_file in fragment_files:
            try:
                with open(fragment_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                instructions = []
                if isinstance(data, dict):
                    instructions = data.get("instructions", [])
                elif isinstance(data, list):
                    instructions = data
                else:
                    logger.warning(f"Unexpected data format in {fragment_file}")
                    continue
                
                # 合并样本（避免重复）
                for result in instructions:
                    if not isinstance(result, dict):
                        continue
                    
                    sample_id = result.get("sample_id", "")
                    instruction_id = result.get("instruction_id", "")
                    model_name = result.get("model", "")
                    domain_name = result.get("domain", "")
                    if not sample_id or not instruction_id or not model_name:
                        continue

                    sample_key = f"{domain_name}/{sample_id}/{instruction_id}/{model_name}"
                    if sample_key in seen_keys:
                        # 如果已存在，合并指标（保留已有指标，更新新指标）
                        for i, existing_result in enumerate(all_results):
                            existing_key = f"{existing_result.get('domain', '')}/{existing_result.get('sample_id')}/{existing_result.get('instruction_id')}/{existing_result.get('model')}"
                            if existing_key == sample_key:
                                existing_metrics = existing_result.get("metrics", {})
                                new_metrics = result.get("metrics", {})
                                for metric_name, metric_value in new_metrics.items():
                                    existing_metrics[metric_name] = metric_value
                                all_results[i]["metrics"] = existing_metrics
                                # 更新其他字段
                                if "instruction_level" in result:
                                    all_results[i]["instruction_level"] = result["instruction_level"]
                                if "domain" in result:
                                    all_results[i]["domain"] = result["domain"]
                                break
                    else:
                        # 新样本，直接添加
                        all_results.append(result)
                        seen_keys.add(sample_key)
            except Exception as e:
                logger.warning(f"Failed to merge fragment file {fragment_file}: {e}")
                continue
        
        logger.info(f"Merged {len(all_results)} unique results from {len(fragment_files)} fragment files")
        return all_results
    
    def _regenerate_csv_results(self, output_dir: Path):
        """
        从分片文件合并后重新生成所有CSV文件（以及可选的合并后的 detailed_results.json）
        这个方法在所有样本评估完成后调用，确保CSV文件包含所有结果
        
        Args:
            output_dir: 输出目录
        """
        # 合并所有分片文件
        all_results = self._merge_fragment_files(output_dir)
        
        if not all_results:
            logger.warning("No results found in fragment files, skipping CSV generation")
            return
        
        # 生成合并后的 detailed_results.json（从所有分片文件合并生成）
        # 包含 success 字段用于后续清理
        try:
            json_path = output_dir / "detailed_results.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({"instructions": all_results}, f, indent=2, ensure_ascii=False)
            logger.info(f"Generated merged detailed_results.json with {len(all_results)} results (includes success field for cleanup)")
        except Exception as e:
            logger.warning(f"Failed to generate merged detailed_results.json: {e}")
        
        # 生成CSV
        try:
            self._save_csv_results(all_results, output_dir)
            logger.info("CSV files generated successfully")
        except Exception as e:
            logger.error(f"Failed to regenerate CSV files: {e}", exc_info=True)
    
    def _save_results(
        self, 
        results: List[Dict[str, Any]], 
        output_dir: Path,
        existing_results: Optional[Dict[str, Dict]] = None
    ):
        """保存评估结果（合并已有结果）"""
        # 合并已有结果
        if existing_results:
            # 将新结果合并到已有结果中
            for result in results:
                sample_key = f"{result.get('domain', '')}/{result['sample_id']}/{result['instruction_id']}/{result['model']}"
                if sample_key in existing_results:
                    # existing_results[sample_key] 现在是完整的结果对象
                    existing_result = existing_results[sample_key]
                    existing_metrics = existing_result.get("metrics", {})
                    new_metrics = result.get("metrics", {})
                    # 合并指标
                    existing_metrics.update(new_metrics)
                    result["metrics"] = existing_metrics
                    # 如果新结果缺少 instruction_level，从已有结果中恢复
                    if "instruction_level" not in result and "instruction_level" in existing_result:
                        result["instruction_level"] = existing_result["instruction_level"]
        
        # 读取所有已有结果（用于CSV生成，确保包含所有模型）
        json_path = output_dir / "detailed_results.json"
        all_existing_samples = []
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    all_existing_samples = data.get("instructions", [])
                elif isinstance(data, list):
                    all_existing_samples = data
            except Exception as e:
                logger.warning(f"Failed to load existing JSON for CSV generation: {e}")
        
        # 构建包含所有模型的结果列表（用于JSON和CSV）
        # 创建新结果的映射
        new_results_map = {f"{r.get('domain', '')}/{r['sample_id']}/{r['instruction_id']}/{r['model']}": r for r in results}
        # 合并已有结果（排除已被新结果覆盖的）
        all_results = []
        for existing_sample in all_existing_samples:
            sample_key = f"{existing_sample.get('domain', '')}/{existing_sample.get('sample_id')}/{existing_sample.get('instruction_id')}/{existing_sample.get('model')}"
            if sample_key not in new_results_map:
                all_results.append(existing_sample)
        # 添加新结果
        all_results.extend(results)
        
        # 保存JSON格式的详细结果（原子写入）- 包含所有模型
        temp_path = json_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump({"instructions": all_results}, f, indent=2, ensure_ascii=False)
        temp_path.replace(json_path)  # 原子替换
        
        # 保存CSV格式的汇总结果（包含所有已有模型）
        self._save_csv_results(all_results, output_dir)
    
    def _save_csv_results(self, results: List[Dict[str, Any]], output_dir: Path):
        """保存CSV格式的结果"""
        # 检查是否有结果
        if not results:
            logger.warning("No results to save to CSV. This may indicate that no model directories were found.")
            return
        
        # 展开结果到DataFrame
        rows = []
        for result in results:
            row = {
                "sample_id": result["sample_id"],
                "domain": result["domain"],
                "instruction_id": result["instruction_id"],
                "model": result["model"],
                "instruction_level": result.get("instruction_level", "unknown")
            }
            
            # 添加每个指标的分数
            for metric_name, metric_result in result["metrics"].items():
                row[metric_name] = metric_result["score"]
                # 添加详细信息
                details = metric_result["details"]
                if "correct_modification_score" in details:
                    row["correct_modification_score"] = details["correct_modification_score"]
                if "no_unintended_modification_score" in details:
                    row["no_unintended_modification_score"] = details["no_unintended_modification_score"]
                if "semantic_understanding_score" in details:
                    row["semantic_understanding_score"] = details["semantic_understanding_score"]
                if "improvement_quality_score" in details:
                    row["improvement_quality_score"] = details["improvement_quality_score"]
                if "aesthetic_achievement_score" in details:
                    row["aesthetic_achievement_score"] = details["aesthetic_achievement_score"]
                if "overall_semantic_completion_score" in details:
                    row["overall_semantic_completion_score"] = details["overall_semantic_completion_score"]
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # 检查DataFrame是否为空
        if df.empty:
            logger.warning("DataFrame is empty. No results to save. This may indicate that no model directories were found.")
            return
        
        if "model" not in df.columns:
            logger.warning("DataFrame is missing 'model' column. Skipping CSV export.")
            return
        
        # 只保存所有模型的对比结果（不保存按模型分组的 CSV）
        all_models_path = output_dir / "all_models_comparison.csv"
        df.to_csv(all_models_path, index=False, encoding='utf-8')
        
        # 保存统计摘要（只保存汇总的统计，不保存按模型分组的）
        self._save_summary_statistics(df, output_dir)
        
        # SCS 按维度分层统计（评估模型在不同维度上的表现）
        self._save_scs_by_dimension_statistics(results, output_dir)
    
    def _save_summary_statistics(self, df: pd.DataFrame, output_dir: Path):
        """保存统计摘要（所有模型的汇总统计）"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            logger.warning("No numeric columns found for summary statistics")
            return
        
        # 按模型分组统计（汇总所有模型）
        summary_rows = []
        for model in df["model"].unique():
            model_df = df[df["model"] == model]
            summary_row = {"model": model}
            for col in numeric_cols:
                summary_row[f"{col}_mean"] = model_df[col].mean()
                summary_row[f"{col}_median"] = model_df[col].median()
                summary_row[f"{col}_std"] = model_df[col].std()
                summary_row[f"{col}_min"] = model_df[col].min()
                summary_row[f"{col}_max"] = model_df[col].max()
                summary_row[f"{col}_count"] = len(model_df[model_df[col].notna()])
            summary_rows.append(summary_row)
        
        summary_df = pd.DataFrame(summary_rows)
        summary_df = summary_df.round(3)
        
        # 只保存汇总的统计文件
        summary_path = output_dir / "all_models_summary_statistics.csv"
        summary_df.to_csv(summary_path, index=False, encoding='utf-8')
        
        # 按指令难度分层统计（所有模型的汇总）
        if "instruction_level" in df.columns:
            by_instruction_all = df.groupby(["model", "instruction_level"])[numeric_cols].agg(['mean', 'count'])
            by_instruction_all = by_instruction_all.round(3)
            by_instruction_path = output_dir / "all_models_by_instruction_difficulty.csv"
            by_instruction_all.to_csv(by_instruction_path, encoding='utf-8')
        
        # 注意：按图片难度分层的统计需要后续通过 notebook 分析后添加（根据 gemini 生成的描述 + XML token 数划分）
        # 不在自动评估中生成
    
    def _save_scs_by_dimension_statistics(self, results: List[Dict[str, Any]], output_dir: Path):
        """
        保存 SCS 按维度分层的统计（评估模型在不同维度上的表现）
        
        Args:
            results: 所有评估结果列表
            output_dir: 输出目录
        """
        # 提取所有 SCS 的维度得分
        scs_rows = []
        
        # Task2的维度名称
        dimension_names = ["style_consistency", "aesthetic_quality"]
        
        for result in results:
            model = result.get("model", "unknown")
            sample_id = result.get("sample_id", "unknown")
            domain = result.get("domain", "unknown")
            instruction_id = result.get("instruction_id", "unknown")
            
            # 获取 style_consistency_score_task2 指标的结果
            scs_metric = result.get("metrics", {}).get("style_consistency_score_task2")
            if not scs_metric or not isinstance(scs_metric, dict):
                continue
            
            # 获取 dimension_scores
            details = scs_metric.get("details", {})
            dimension_scores = details.get("dimension_scores", {})
            
            if not dimension_scores or not isinstance(dimension_scores, dict):
                continue
            
            # 提取每个维度的得分
            for dimension_name in dimension_names:
                dimension_score = dimension_scores.get(dimension_name)
                if dimension_score is None:
                    continue
                
                # 确保得分是数值类型
                try:
                    score = float(dimension_score)
                except (ValueError, TypeError):
                    continue
                
                scs_rows.append({
                    "model": model,
                    "sample_id": sample_id,
                    "domain": domain,
                    "instruction_id": instruction_id,
                    "dimension": dimension_name,
                    "score": score
                })
        
        if not scs_rows:
            logger.info("No SCS dimension scores found, skipping SCS by dimension statistics")
            return
        
        # 转换为 DataFrame
        scs_df = pd.DataFrame(scs_rows)
        
        # 按模型和维度分组统计
        summary_rows = []
        for model in scs_df["model"].unique():
            model_df = scs_df[scs_df["model"] == model]
            
            for dimension in model_df["dimension"].unique():
                dim_df = model_df[model_df["dimension"] == dimension]
                
                mean_score = dim_df["score"].mean()
                std_score = dim_df["score"].std()
                min_score = dim_df["score"].min()
                max_score = dim_df["score"].max()
                count = len(dim_df)
                
                summary_rows.append({
                    "model": model,
                    "dimension": dimension,
                    "mean_score": round(mean_score, 2),
                    "std_score": round(std_score, 2) if not pd.isna(std_score) else 0.0,
                    "min_score": round(min_score, 2),
                    "max_score": round(max_score, 2),
                    "count": int(count)
                })
        
        if not summary_rows:
            logger.warning("No summary rows generated for SCS by dimension statistics")
            return
        
        summary_df = pd.DataFrame(summary_rows)
        summary_df = summary_df.sort_values(["model", "dimension"])
        
        # 保存统计文件
        scs_summary_path = output_dir / "all_models_scs_by_dimension.csv"
        summary_df.to_csv(scs_summary_path, index=False, encoding='utf-8')
        logger.info(f"Saved SCS by dimension statistics to {scs_summary_path}")
