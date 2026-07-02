"""
任务二评估指标实现
"""

import logging
import json
import re
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
import xml.etree.ElementTree as ET
import time

from eval.base import BaseMetric, MetricResult
from src.llm.client import LLMClient
from src.renderer.drawio_renderer import DrawioRenderer

logger = logging.getLogger(__name__)

# 评估模型配置：优先从环境变量 CUSTOM_VISION_MODEL 读取，否则使用默认值
EVAL_MODEL = os.getenv('CUSTOM_VISION_MODEL', 'gemini-3-pro-preview')


def count_tokens_offline(text: str, tokenizer_name: str = "cl100k_base") -> tuple[int, str]:
    """
    Count tokens without making first-run smoke tests depend on tiktoken cache/network.

    By default this uses a stable character-length approximation. Set
    VCG_USE_TIKTOKEN=1 to enable exact tiktoken counting in environments where
    the tokenizer files are already available or network access is acceptable.
    """
    if os.getenv("VCG_USE_TIKTOKEN", "").lower() in {"1", "true", "yes"}:
        try:
            import tiktoken

            tokenizer = tiktoken.get_encoding(tokenizer_name)
            return len(tokenizer.encode(text)), tokenizer_name
        except Exception as e:
            logger.warning(
                "Failed to load tokenizer %s (%s); using approximate token count",
                tokenizer_name,
                e,
            )

    return max(1, len(text) // 4), "approximate_char_div_4"


class ModifiedXMLExecutionSuccessRate(BaseMetric):
    """修改后XML成功执行率"""
    
    def __init__(self, renderer: Optional[DrawioRenderer] = None):
        super().__init__("modified_xml_execution_success_rate")
        self.renderer = renderer
    
    def evaluate(
        self,
        modified_xml_path: Path,
        modified_rendered_path: Optional[Path] = None,
        **kwargs
    ) -> MetricResult:
        """评估修改后XML是否能够成功执行"""
        try:
            if not modified_xml_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={"error": "Modified XML file not found"},
                    success=False,
                    error_message="Modified XML file not found"
                )
            
            execution_success = True
            render_success = False
            error_message = None
            
            if modified_rendered_path:
                render_success = modified_rendered_path.exists()
                execution_success = render_success
            else:
                # 尝试渲染
                if self.renderer:
                    try:
                        from src.core.models import DiagramXML
                        xml_content = modified_xml_path.read_text(encoding='utf-8')
                        diagram = DiagramXML(content=xml_content)
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            tmp_path = Path(tmp.name)
                            self.renderer.render(diagram, tmp_path)
                            render_success = tmp_path.exists()
                            execution_success = render_success
                            tmp_path.unlink()
                    except Exception as e:
                        error_message = str(e)
                        execution_success = False
                        render_success = False
            
            return MetricResult(
                metric_name=self.name,
                score=1.0 if execution_success else 0.0,
                details={
                    "execution_success": execution_success,
                    "render_success": render_success,
                    "xml_valid": True,
                    "error_message": error_message
                },
                success=True
            )
        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )


class ModifiedXMLTokenCount(BaseMetric):
    """修改后XML Token数量"""
    
    def __init__(self, tokenizer_name: str = "cl100k_base"):
        super().__init__("modified_xml_token_count")
        self.tokenizer_name = tokenizer_name
    
    def evaluate(self, modified_xml_path: Path, **kwargs) -> MetricResult:
        """统计修改后XML Token数量"""
        try:
            if not modified_xml_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={"error": "Modified XML file not found"},
                    success=False,
                    error_message="Modified XML file not found"
                )
            
            xml_content = modified_xml_path.read_text(encoding='utf-8')
            token_count, tokenizer_used = count_tokens_offline(xml_content, self.tokenizer_name)
            
            return MetricResult(
                metric_name=self.name,
                score=float(token_count),
                details={
                    "xml_token_count": token_count,
                    "xml_length": len(xml_content),
                    "tokenizer": tokenizer_used
                },
                success=True
            )
        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )


class EditPrecision(BaseMetric):
    """编辑精度"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("edit_precision")
        self.llm_client = llm_client
    
    def evaluate(
        self,
        original_rendered_path: Path,
        instruction_path: Path,
        modified_rendered_path: Path,
        original_xml_path: Optional[Path] = None,
        modified_xml_path: Optional[Path] = None,
        **kwargs
    ) -> MetricResult:
        """评估编辑精度"""
        try:
            instruction = instruction_path.read_text(encoding='utf-8')
            
            # 优先使用XML进行精确评估
            if original_xml_path and modified_xml_path and original_xml_path.exists() and modified_xml_path.exists():
                return self._evaluate_from_xml(original_xml_path, modified_xml_path, instruction)
            else:
                # 使用LLM视觉评估
                if not self.llm_client:
                    return MetricResult(
                        metric_name=self.name,
                        score=0.0,
                        details={"error": "LLM client not provided"},
                        success=False,
                        error_message="LLM client not provided"
                    )
                return self._evaluate_from_images(original_rendered_path, instruction, modified_rendered_path)
        except Exception as e:
            logger.error(f"Error in edit precision evaluation: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _evaluate_from_xml(
        self,
        original_xml_path: Path,
        modified_xml_path: Path,
        instruction: str
    ) -> MetricResult:
        """基于XML的精确评估"""
        try:
            original_elements = self._parse_xml_elements(original_xml_path)
            modified_elements = self._parse_xml_elements(modified_xml_path)
            
            should_modify = self._identify_elements_to_modify(instruction, original_elements)
            actually_modified = self._identify_modified_elements(original_elements, modified_elements)
            
            correctly_modified = set(should_modify) & set(actually_modified)
            should_modify_but_not = set(should_modify) - set(actually_modified)
            unintended_modified = set(actually_modified) - set(should_modify)
            
            correct_score = len(correctly_modified) / len(should_modify) if should_modify else 1.0
            no_unintended_score = 1.0 - (len(unintended_modified) / len(original_elements)) if original_elements else 1.0
            
            edit_precision_score = (correct_score * 0.7) + (no_unintended_score * 0.3)
            
            return MetricResult(
                metric_name=self.name,
                score=edit_precision_score,
                details={
                    "correct_modification_score": correct_score,
                    "no_unintended_modification_score": no_unintended_score,
                    "correctly_modified_elements": list(correctly_modified),
                    "should_modify_but_not_modified": list(should_modify_but_not),
                    "unintended_modified_elements": list(unintended_modified)
                },
                success=True
            )
        except Exception as e:
            logger.error(f"Error in XML-based evaluation: {e}")
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _evaluate_from_images(
        self,
        original_rendered_path: Path,
        instruction: str,
        modified_rendered_path: Path
    ) -> MetricResult:
        """基于LLM的视觉评估"""
        try:
            prompt = self._get_prompt(original_rendered_path, instruction, modified_rendered_path)
            response, _ = self.llm_client._call_vision_api(
                prompt=prompt,
                image_input=modified_rendered_path,
                provider="custom",
                model=EVAL_MODEL,
                temperature=0.3
            )
            
            result = self._parse_response(response)
            
            return MetricResult(
                metric_name=self.name,
                score=result.get("edit_precision_score", 0.0),
                details=result,
                success=True
            )
        except Exception as e:
            logger.error(f"Error in image-based evaluation: {e}")
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _parse_xml_elements(self, xml_path: Path) -> List[str]:
        """解析XML，提取元素ID列表"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            elements = []
            for cell in root.findall('.//mxCell'):
                element_id = cell.get('id')
                if element_id:
                    elements.append(element_id)
            return elements
        except Exception as e:
            logger.error(f"Error parsing XML: {e}")
            return []
    
    def _identify_elements_to_modify(self, instruction: str, elements: List[str]) -> List[str]:
        """根据指令识别应该修改的元素"""
        # 简单的启发式规则：从指令中提取元素ID或名称
        should_modify = []
        instruction_lower = instruction.lower()
        for elem_id in elements:
            if elem_id.lower() in instruction_lower:
                should_modify.append(elem_id)
        return should_modify
    
    def _identify_modified_elements(self, original: List[str], modified: List[str]) -> List[str]:
        """识别实际被修改的元素"""
        # 通过对比XML属性变化来识别
        # 这里简化处理，实际应该对比属性值
        modified_set = set(modified)
        original_set = set(original)
        
        # 新增的元素
        new_elements = modified_set - original_set
        # 删除的元素（在原始中但不在修改后中）
        deleted_elements = original_set - modified_set
        
        # 返回所有变化的元素
        return list(new_elements | deleted_elements)
    
    def _get_prompt(self, original_path: Path, instruction: str, modified_path: Path) -> str:
        """生成评估Prompt"""
        return f"""You are a professional diagram editing precision evaluation expert. Please evaluate whether the model only modified the parts required by the instruction without unintended modifications to other parts.

## Original Image (Gemini Rendered)
[Image: {original_path}]

## Modification Instruction
{instruction}

## Modified Image by Model
[Image: {modified_path}]

## Evaluation Task

Please carefully analyze the two images and the modification instruction to complete the following tasks:

1. **Identify elements that should be modified** (based on the instruction)
2. **Identify elements that were actually modified** (by comparing the two images)
3. **Calculate editing precision**

## Evaluation Dimensions

Please evaluate from the following dimensions (score 0-1, where 1 is perfect):

### 1. Correct Modification Score
- Were all elements required to be modified by the instruction correctly modified?

### 2. No Unintended Modification Score
- Were any elements that should not be modified unintentionally modified?

## Output Format (Strict JSON)

```json
{{
  "edit_precision_score": 0.92,
  "correct_modification_score": 0.95,
  "no_unintended_modification_score": 0.88,
  "should_modify_elements": ["Node A", "Node B"],
  "correctly_modified_elements": ["Node A", "Node B"],
  "should_modify_but_not_modified": [],
  "unintended_modified_elements": ["Node C"],
  "detailed_reasoning": "The model successfully modified Node A and Node B as required by the instruction, but unintentionally modified the color of Node C. Overall editing precision is high."
}}
```

Please analyze carefully and output JSON:"""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "edit_precision_score": 0.0,
                    "correct_modification_score": 0.0,
                    "no_unintended_modification_score": 0.0,
                    "detailed_reasoning": "Failed to parse response"
                }
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return {
                "edit_precision_score": 0.0,
                "correct_modification_score": 0.0,
                "no_unintended_modification_score": 0.0,
                "detailed_reasoning": f"Parse error: {e}"
            }


class SemanticInstructionCompletion(BaseMetric):
    """语义指令完成度"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("semantic_instruction_completion")
        self.llm_client = llm_client
    
    def evaluate(
        self,
        original_rendered_path: Path,
        instruction_path: Path,
        modified_rendered_path: Path,
        **kwargs
    ) -> MetricResult:
        """评估语义指令完成度"""
        if not self.llm_client:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "LLM client not provided"},
                success=False,
                error_message="LLM client not provided"
            )
        
        try:
            instruction = instruction_path.read_text(encoding='utf-8')
            
            # 判断是否包含主观描述
            has_subjective = self._has_subjective_descriptions(instruction)
            
            if not has_subjective:
                return MetricResult(
                    metric_name=self.name,
                    score=1.0,  # 如果没有主观描述，认为完成度是1.0
                    details={
                        "instruction_has_subjective_parts": False,
                        "note": "Instruction does not contain subjective descriptions"
                    },
                    success=True
                )
            
            prompt = self._get_prompt(original_rendered_path, instruction, modified_rendered_path)
            response, _ = self.llm_client._call_vision_api(
                prompt=prompt,
                image_input=modified_rendered_path,
                provider="custom",
                model=EVAL_MODEL,
                temperature=0.3
            )
            
            result = self._parse_response(response)
            
            return MetricResult(
                metric_name=self.name,
                score=result.get("overall_semantic_completion_score", 0.0),
                details=result,
                success=True
            )
        except Exception as e:
            logger.error(f"Error in semantic instruction completion evaluation: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _has_subjective_descriptions(self, instruction: str) -> bool:
        """判断指令是否包含主观描述"""
        subjective_keywords = [
            "compact", "loose", "tight", "spacious", "align", "arrange", "spacing", "layout", "evenly", "uniform",
            "light", "dark", "pale", "bright", "vivid", "color scheme", "color", "coordinate", "harmonious",
            "modern", "traditional", "minimalist", "simple", "complex", "professional", "elegant", "style", "aesthetic",
            "layered", "contrast", "balanced", "unified", "visual", "clear", "clearer",
            "more", "slightly", "a bit", "very", "much", "less", "better", "improved"
        ]

        instruction_lower = instruction.lower()
        return any(keyword in instruction_lower for keyword in subjective_keywords)
    
    def _get_prompt(self, original_path: Path, instruction: str, modified_path: Path) -> str:
        """生成评估Prompt"""
        return f"""You are a professional diagram semantic understanding and aesthetic evaluation expert. Please evaluate the model's completion quality for the ambiguous and subjective parts of the instruction.

## Original Image (Gemini Rendered)
[Image: {original_path}]

## Modification Instruction
{instruction}

## Modified Image by Model
[Image: {modified_path}]

## Evaluation Task

Please analyze whether the instruction contains **ambiguous, subjective descriptions** (such as "more compact", "light color scheme", "more modern", etc.). These descriptions typically:
- Have strong subjectivity without clear quantifiable standards
- Require understanding of semantic intent and aesthetic requirements
- Evaluation focuses on "semantic understanding" and "aesthetic effect" levels of completion quality

If the instruction contains subjective descriptions, please evaluate the model's completion quality for these parts from the following three dimensions:

### 1. Semantic Understanding
- Did the model understand the semantic intent of the ambiguous descriptions in the instruction?

### 2. Improvement Quality
- Does the improvement meet the requirements of the subjective descriptions in the instruction?
- Is the improvement natural and harmonious?

### 3. Aesthetic Achievement
- Did it achieve the aesthetic effect required by the instruction?

## Output Format (Strict JSON)

```json
{{
  "semantic_understanding_score": 0.92,
  "improvement_quality_score": 0.88,
  "aesthetic_achievement_score": 0.90,
  "overall_semantic_completion_score": 0.90,
  "instruction_has_subjective_parts": true,
  "subjective_parts_detected": ["more compact layout"],
  "detailed_reasoning": "The model well understood the intent of 'more compact layout' instruction and achieved a compact effect by reducing element spacing and optimizing layout. The overall improvement is natural and harmonious, meeting the instruction requirements."
}}
```

Please analyze carefully and output JSON:"""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "semantic_understanding_score": 0.0,
                    "improvement_quality_score": 0.0,
                    "aesthetic_achievement_score": 0.0,
                    "overall_semantic_completion_score": 0.0,
                    "detailed_reasoning": "Failed to parse response"
                }
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return {
                "semantic_understanding_score": 0.0,
                "improvement_quality_score": 0.0,
                "aesthetic_achievement_score": 0.0,
                "overall_semantic_completion_score": 0.0,
                "detailed_reasoning": f"Parse error: {e}"
            }


class ModificationJSONTokenCount(BaseMetric):
    """修改 JSON Token 数量 (MJTC)"""
    
    def __init__(self, tokenizer_name: str = "cl100k_base"):
        super().__init__("modification_json_token_count")
        self.tokenizer_name = tokenizer_name
    
    def _get_relative_path(self, path: Path) -> str:
        """
        将绝对路径转换为相对路径（相对于包含task2_benchmark的目录）
        
        Args:
            path: 绝对路径
            
        Returns:
            相对路径字符串
        """
        path_str = str(path)
        
        # Prefer paths relative to the benchmark/demo root to avoid leaking
        # machine-specific absolute paths into evaluation outputs.
        for benchmark_marker in ("task2_benchmark", "task2_demo"):
            parts = Path(path_str).parts
            try:
                marker_idx = parts.index(benchmark_marker)
                rel_parts = parts[marker_idx:]
                return str(Path(*rel_parts))
            except ValueError:
                continue

        # Fallback for custom benchmark roots: keep the path from domain_* onward.
        parts = Path(path_str).parts
        for idx, part in enumerate(parts):
            if part.startswith("domain_"):
                return str(Path(*parts[idx:]))
        
        # 如果找不到可识别的benchmark根，返回原始路径
        return path_str
    
    def evaluate(
        self,
        model_output_json_path: Path,
        **kwargs
    ) -> MetricResult:
        """
        计算修改 JSON 的 token 数量
        
        Args:
            model_output_json_path: 模型输出的增量修改 JSON 文件路径
                路径格式：instructions/inst_xxx/model_xxx/model_output.json
        """
        try:
            if not model_output_json_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={"error": f"Model output JSON not found: {model_output_json_path}"},
                    success=False,
                    error_message=f"Model output JSON not found: {model_output_json_path}"
                )
            
            # 读取 JSON 文件
            with open(model_output_json_path, 'r', encoding='utf-8') as f:
                modification_json = json.load(f)
            
            # Convert JSON object to string
            json_str = json.dumps(modification_json, ensure_ascii=False)
            
            # Calculate token count
            token_count, tokenizer_used = count_tokens_offline(json_str, self.tokenizer_name)
            
            # 转换为相对路径（相对于包含task2_benchmark的目录）
            json_path_rel = self._get_relative_path(model_output_json_path)
            
            return MetricResult(
                metric_name=self.name,
                score=float(token_count),
                details={
                    "token_count": token_count,
                    "json_length": len(json_str),
                    "json_path": json_path_rel,
                    "tokenizer": tokenizer_used
                },
                success=True
            )
        except Exception as e:
            logger.error(f"Error computing MJTC: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )


class StyleConsistencyScoreTask2(BaseMetric):
    """
    Style Consistency Score (SCS) for Task 2
    Evaluates style and aesthetic consistency between Gemini's original rendered image and the model's modified rendered image.
    
    Important: Only evaluates style consistency and aesthetic quality, NOT element completeness or text consistency.
    Modified diagrams will have changes (elements may be deleted, added, modified), which is normal.
    We only focus on whether the unmodified parts maintain the original style and aesthetic.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("style_consistency_score_task2")
        self.llm_client = llm_client
    
    def evaluate(
        self,
        gemini_rendered_path: Path,
        modified_rendered_path: Path,
        execution_success: bool = True,
        **kwargs
    ) -> MetricResult:
        """
        Evaluate style consistency for Task 2 (modified diagram vs original diagram)
        
        Args:
            gemini_rendered_path: Gemini original rendered image path
            modified_rendered_path: Model modified rendered image path
            execution_success: Whether the modified XML executed successfully
        """
        if not self.llm_client:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "LLM client not provided"},
                success=False,
                error_message="LLM client not provided"
            )
        
        # If execution failed, return 0.0 directly
        if not execution_success:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={
                    "execution_success": False,
                    "note": "Execution failed, SCS = 0.0"
                },
                success=True
            )
        
        # Check if rendered image exists
        if not modified_rendered_path.exists():
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "Modified rendered image not found"},
                success=False,
                error_message="Modified rendered image not found"
            )
        
        # Use evaluation model from environment variable or default
        eval_model = EVAL_MODEL
        
        prompt = self._build_scs_prompt(gemini_rendered_path, modified_rendered_path)
        
        try:
            response, _ = self.llm_client._call_vision_api(
                prompt=prompt,
                image_input=[gemini_rendered_path, modified_rendered_path],
                provider="custom",
                model=eval_model,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            result = json.loads(response)
            score = result.get("final_score", 0.0)
            
            # If final_score doesn't exist, try to calculate from dimension_scores
            if score == 0.0 and "analysis" in result:
                dim_scores = result["analysis"].get("dimension_scores", {})
                if dim_scores:
                    # Task 2 has only two dimensions: style_consistency and aesthetic_quality
                    avg_score = (
                        dim_scores.get("style_consistency", 0) +
                        dim_scores.get("aesthetic_quality", 0)
                    ) / 2.0
                    score = avg_score / 10.0  # Normalize to 0-1
            
            # Ensure score is in 0-1 range
            score = max(0.0, min(1.0, score))
            
            logger.info(f"SCS (Task2) evaluation: dimension_scores={result.get('analysis', {}).get('dimension_scores', {})}, final_score={score}")
            
            # 转换为相对路径（相对于包含task2_benchmark的目录）
            gemini_rendered_path_rel = self._get_relative_path(gemini_rendered_path)
            modified_rendered_path_rel = self._get_relative_path(modified_rendered_path)
            
            return MetricResult(
                metric_name=self.name,
                score=float(score),
                details={
                    "style_consistency_score": float(score),
                    "gemini_rendered_path": gemini_rendered_path_rel,
                    "modified_rendered_path": modified_rendered_path_rel,
                    "dimension_scores": result.get("analysis", {}).get("dimension_scores", {}),
                    "analysis": result.get("analysis", {})
                },
                success=True
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse SCS response as JSON: {e}, trying fallback parsing")
            # Fallback to simple float parsing
            try:
                import re
                score_match = re.search(r'\d+\.?\d*', response)
                if score_match:
                    score = float(score_match.group())
                    score = max(0.0, min(1.0, score / 10.0 if score > 1.0 else score))
                else:
                    score = 0.0
            except Exception:
                score = 0.0
            
            # 转换为相对路径（相对于包含task2_benchmark的目录）
            gemini_rendered_path_rel = self._get_relative_path(gemini_rendered_path)
            modified_rendered_path_rel = self._get_relative_path(modified_rendered_path)
            
            return MetricResult(
                metric_name=self.name,
                score=float(score),
                details={
                    "style_consistency_score": float(score),
                    "gemini_rendered_path": gemini_rendered_path_rel,
                    "modified_rendered_path": modified_rendered_path_rel,
                    "error": f"Failed to parse response: {e}",
                    "fallback_score": score
                },
                success=True
            )
        except Exception as e:
            error_str = str(e).lower()
            # 检测 524 错误并记录警告
            if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                logger.error(f"HTTP 524 Cloudflare timeout error when evaluating SCS (Task2): {e}", exc_info=True)
                logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request, which could result in billing.")
            else:
                logger.error(f"Error evaluating SCS (Task2): {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _get_relative_path(self, path: Path) -> str:
        """
        将绝对路径转换为相对路径（相对于包含task2_benchmark的目录）
        
        Args:
            path: 绝对路径
            
        Returns:
            相对路径字符串
        """
        path_str = str(path)
        
        # 查找task2_benchmark在路径中的位置
        benchmark_marker = "task2_benchmark"
        if benchmark_marker in path_str:
            # 找到task2_benchmark目录
            parts = Path(path_str).parts
            try:
                benchmark_idx = parts.index(benchmark_marker)
                # 相对路径从task2_benchmark开始
                rel_parts = parts[benchmark_idx:]
                return str(Path(*rel_parts))
            except ValueError:
                pass
        
        # 如果找不到task2_benchmark，返回原始路径
        return path_str
    
    def _build_scs_prompt(self, gemini_rendered_path: Path, modified_rendered_path: Path) -> str:
        """Build SCS evaluation prompt (English version, only style and aesthetic)"""
        return f"""You are a professional diagram design reviewer. Please compare the "Original Diagram (Gemini generated)" and the "Modified Diagram (Model generated)" to evaluate whether the modified diagram maintains the original **style and aesthetic**.

**Important Notes**:
- The modified diagram will definitely have changes (elements may be deleted, added, modified), which is **normal** and should not result in score deduction
- **Only evaluate style consistency and aesthetic consistency**, do not evaluate element completeness, text consistency, or other content consistency
- We focus on: whether the modified diagram overall still conforms to the original diagram's style and aesthetic standards

Original Diagram (Gemini generated):
[Image: {gemini_rendered_path}]

Modified Diagram (Model generated):
[Image: {modified_rendered_path}]

**Evaluation Steps:**

**Step 1: Style Attribute Extraction**
Please carefully analyze the original diagram and extract the following **style and aesthetic** related key attributes:
- **Color Scheme**: Main color families, tones, saturation characteristics (e.g., "blue family", "warm tones", "high saturation")
- **Font Style**: Overall style characteristics of font weight, size, font family
- **Visual Element Style**: Uniformity of node shapes, uniformity of line styles, overall visual style
- **Aesthetic Features**: Overall layout balance, alignment methods, visual hierarchy, space utilization

**Step 2: Style and Aesthetic Consistency Evaluation**
Evaluate the modified diagram's performance in the following aspects:
- **Color Style Consistency**: Do unmodified parts maintain the original color style? Is the overall color scheme harmonious?
- **Visual Style Consistency**: Do unmodified parts maintain the original visual style (node shapes, line styles, etc.)?
- **Aesthetic Quality**: Is the modified diagram overall still beautiful, balanced, and professional? Are there obvious visual errors (element overlaps, text misalignment, layout chaos)?

**Important Evaluation Principles**:
- ✅ **Should evaluate**: Style consistency of unmodified parts, overall aesthetic quality, visual errors
- ❌ **Should NOT evaluate**: Whether element counts are consistent, whether text content is consistent, whether elements are complete (these changes are normal)

**Step 3: Dimension Scoring (0-10 scale)**
Please score the following two dimensions separately (0-10 points, keep one decimal place):
1. **Style Consistency** (color style, visual element style, overall style characteristics): ___
   - Evaluate whether unmodified parts maintain the original style characteristics
   - Evaluate whether the overall style is coordinated and unified
2. **Aesthetic Quality** (visual balance, alignment, overall beauty, presence of obvious visual errors): ___
   - Evaluate whether the modified diagram is still beautiful and professional
   - If there are obvious visual errors (element overlaps, text misalignment, layout chaos), deduct points

**Step 4: Final Score Calculation**
- Calculate the average of the two dimension scores
- Divide the average by 10 to normalize to 0-1
- Example: Dimension scores [8.5, 9.0], average = 8.75, final score = 0.875

**Output Format (JSON):**
{{
    "analysis": {{
        "original_style_attributes": {{
            "color_scheme": "...",
            "font_style": "...",
            "visual_element_style": "...",
            "aesthetic_features": "..."
        }},
        "style_consistency_analysis": "...",
        "aesthetic_quality_analysis": "...",
        "visual_errors": [
            "Visual error description (if any)"
        ],
        "dimension_scores": {{
            "style_consistency": 8.5,
            "aesthetic_quality": 9.0
        }},
        "average_score": 8.75
    }},
    "final_score": 0.875
}}

**Important Notes**:
- Please strictly follow the scoring standards, avoid directly giving high scores (0.85+)
- Must complete attribute extraction and consistency analysis before giving dimension scores
- **Do not deduct points for element count changes or text content changes**, these are normal modification results
- **Only focus on style and aesthetic**: If the modified diagram has unified style and good aesthetics, even if content has changed, it should receive a high score
- If the modified diagram has obvious visual errors (element overlaps, text misalignment, layout chaos), deduct points in the "Aesthetic Quality" dimension
- Final score must be calculated based on the average of dimension scores, cannot be directly estimated
"""


class XDRFR(BaseMetric):
    """
    XML-based DRFR (XDRFR) - Instruction Following Evaluation based on XML Code
    
    Core Features:
    1. Completely based on XML code evaluation, does not depend on rendered images
    2. Only uses decomposed questions (no common questions)
    3. Only passes text input (XML code) to the model, no images (uses evaluation model from CUSTOM_VISION_MODEL env var or default gemini-3-pro-preview)
    4. Questions focus on XML code-level modifications (attribute values, element existence, structural changes, etc.)
    
    Important: Instructions use natural language (based on rendered images), but evaluation needs to map natural language to XML code.
    Note: Uses evaluation model from CUSTOM_VISION_MODEL env var or default gemini-3-pro-preview (same as other metrics), but only passes text input, not images.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("xdrfr")
        self.llm_client = llm_client

    def evaluate(
        self,
        model_output_json: Dict[str, Any],
        instruction: str,
        decomposed_questions: List[str],
        execution_success: bool = True,
        **kwargs
    ) -> MetricResult:
        """
        Evaluate XML-based DRFR (XDRFR)
        
        Args:
            model_output_json: Model output JSON containing incremental modifications (Dict)
            instruction: Modification instruction (natural language)
            decomposed_questions: Decomposed questions (model generated, List[str])
            execution_success: Whether the modified XML executed successfully
        """
        if not self.llm_client:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "LLM client not provided"},
                success=False,
                error_message="LLM client not provided"
            )
        
        # 注意：即使渲染失败（execution_success=False），也会参与评估
        # 因为现在输入的是模型生成的增量修改JSON，可以直接基于JSON进行评估
        
        # Check if model_output_json exists and is valid
        if not model_output_json or not isinstance(model_output_json, (dict, list)):
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={
                    "xdrfr_score": 0.0,
                    "total_questions": len(decomposed_questions),
                    "satisfied_count": 0,
                    "per_question_results": [
                        {
                            "question": question,
                            "answer": "No",
                            "is_satisfied": False
                        }
                        for question in decomposed_questions
                    ]
                },
                success=True
            )
        
        # Use evaluation model from environment variable or default
        eval_model = EVAL_MODEL
        
        eval_results = []
        satisfied_count = 0
        
        # 优化：批量处理所有问题，减少API调用次数
        if decomposed_questions and len(decomposed_questions) > 0:
            try:
                # 批量查询所有问题
                sample_info = kwargs.get('sample_info', '')
                batch_results = self._query_evaluation_model_batch(
                    model_output_json=model_output_json,
                    instruction=instruction,
                    questions=decomposed_questions,
                    model=eval_model,
                    sample_info=sample_info
                )
                
                # 检查批量查询是否成功（至少有一个结果）
                if not batch_results or len(batch_results) == 0 or not any(r.get("is_satisfied") is not None for r in batch_results):
                    # 批量查询失败，直接抛出异常，不进行单个查询回退
                    raise Exception(f"Batch query failed: no valid results returned")
                
                # 处理每个问题的结果
                for i, question in enumerate(decomposed_questions):
                    # 获取对应的结果
                    if i < len(batch_results) and batch_results[i].get("is_satisfied") is not None:
                        result = batch_results[i]
                    else:
                        # 批量查询结果不完整，直接抛出异常，不进行单个查询回退
                        raise Exception(f"Batch query result incomplete: missing result for question {i+1}")
                    
                    if result.get("is_satisfied", False):
                        satisfied_count += 1
                    
                    eval_results.append({
                        "question": result.get("question", question),
                        "answer": result.get("answer", "No"),
                        "is_satisfied": result.get("is_satisfied", False)
                    })
            except Exception as e:
                # 批量查询失败，直接抛出异常，不进行单个查询回退
                logger.error(f"Error in batch evaluation: {e}, will save as None for retry")
                raise  # 重新抛出异常，让evaluator捕获并保存为None
        
        # Calculate XDRFR score
        xdrfr_score = satisfied_count / len(decomposed_questions) if decomposed_questions else 0.0
        
        return MetricResult(
            metric_name=self.name,
            score=float(xdrfr_score),
            details={
                "xdrfr_score": float(xdrfr_score),
                "total_questions": len(decomposed_questions),
                "satisfied_count": satisfied_count,
                "per_question_results": eval_results
            },
            success=True
        )
    
    def _query_evaluation_model_batch(
        self,
        model_output_json: Dict[str, Any],
        instruction: str,
        questions: List[str],
        model: str = EVAL_MODEL,
        sample_info: str = ""
    ) -> List[Dict[str, Any]]:
        """
        批量使用评估模型评估所有问题（优化：减少API调用次数）
        
        实现方案1：基于处理时间的预防
        - 设置90秒客户端超时（在Cloudflare超时前主动取消）
        - 监控处理时间，超过80秒标记为高风险
        """
        prompt = self._build_xdrfr_prompt_batch(
            model_output_json=model_output_json,
            instruction=instruction,
            questions=questions
        )
        
        start_time = time.time()
        
        try:
            # Call evaluation model (evaluate all questions at once, only pass text input, no images)
            provider_obj = self.llm_client._get_provider('custom')
            client = provider_obj.get_client()
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # 记录请求开始时间
            request_start = time.time()
            prompt_size = len(prompt)
            # 使用传入的样本信息参数
            if sample_info:
                logger.info(f"{sample_info} Starting XDRFR batch query (Prompt size: {prompt_size:,} chars, Questions: {len(questions)})")
            else:
                logger.info(f"Starting XDRFR batch query (Prompt size: {prompt_size:,} chars, Questions: {len(questions)})")
            
            # 直接调用API，依赖OpenAI SDK的timeout参数（1200秒）
            # 不再使用客户端主动取消机制，因为请求发出即扣费
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            request_duration = time.time() - request_start
            if sample_info:
                logger.info(f"{sample_info} Request completed in {request_duration:.1f}s")
            else:
                logger.info(f"Request completed in {request_duration:.1f}s")
            
            batch_answer = response.choices[0].message.content
            
            # Parse batch answer
            return self._parse_batch_answer(batch_answer, questions)
        except TimeoutError as e:
            # 服务器超时（OpenAI SDK的timeout参数触发，通常是1200秒）
            elapsed = time.time() - start_time
            logger.error(f"Server timeout after {elapsed:.1f}s when querying evaluation model in batch: {e}")
            logger.error("This likely indicates server is slow or overloaded. Please retry later.")
            return []
        except Exception as e:
            error_str = str(e).lower()
            elapsed = time.time() - start_time
            
            # 检测 524 错误并记录警告
            if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                logger.error(f"HTTP 524 Cloudflare timeout error when querying evaluation model in batch (after {elapsed:.1f}s): {e}")
                logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request, which could result in billing.")
            elif 'timeout' in error_str or 'timed out' in error_str:
                logger.error(f"Timeout error when querying evaluation model in batch (after {elapsed:.1f}s): {e}")
                logger.error("Request may have been cancelled or server timed out. Check server status before retrying.")
            else:
                logger.error(f"Error querying evaluation model in batch (after {elapsed:.1f}s): {e}")
            return []
    
    def _query_evaluation_model_single(
        self,
        model_output_json: Dict[str, Any],
        instruction: str,
        question: str,
        model: str = EVAL_MODEL
    ) -> Dict[str, Any]:
        """单个查询评估模型（回退方法）"""
        prompt = self._build_xdrfr_prompt_single(
            model_output_json=model_output_json,
            instruction=instruction,
            question=question
        )
        
        try:
            provider_obj = self.llm_client._get_provider('custom')
            client = provider_obj.get_client()
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            answer = response.choices[0].message.content
            binary_answer, _, _ = self._parse_answer(answer)
            
            return {
                "question": question,
                "answer": binary_answer,
                "is_satisfied": binary_answer == "Yes"
            }
        except Exception as e:
            error_str = str(e).lower()
            # 检测 524 错误并记录警告
            if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                logger.error(f"HTTP 524 Cloudflare timeout error when querying evaluation model for single question: {e}")
                logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request, which could result in billing.")
            else:
                logger.error(f"Error querying evaluation model for single question: {e}")
            return {
                "question": question,
                "answer": "No",
                "is_satisfied": False
            }
    
    def _build_xdrfr_prompt_single(
        self,
        model_output_json: Dict[str, Any],
        instruction: str,
        question: str
    ) -> str:
        """Build XDRFR single evaluation prompt (evaluate one question)"""
        # Convert model_output_json to string format for prompt
        if isinstance(model_output_json, list):
            changes = model_output_json
        elif isinstance(model_output_json, dict) and "changes" in model_output_json:
            changes = model_output_json["changes"]
        else:
            changes = model_output_json if isinstance(model_output_json, list) else [model_output_json]
        
        model_output_json_str = json.dumps(changes, ensure_ascii=False, indent=2)
        
        return f"""You are a professional XML modification evaluation expert. Please answer the following question with "Yes" or "No" based on the provided model output JSON (containing incremental modifications) and modification instruction.

**Important Note**: The modification instruction uses natural language descriptions (based on rendered images). The model output JSON contains incremental modifications in the format of original_fragment and modified_fragment pairs. You need to understand the natural language instruction, then verify whether the modifications in the JSON satisfy the instruction requirements.

**Model Output JSON (Incremental Modifications):**
```json
{model_output_json_str}
```

**Modification Instruction (Natural Language):**
"{instruction}"

**Question:**
{question}

**Requirements:**
- Answer with only "Yes" or "No", do not output any other content
- Do not output reasons, explanations, evidence, or judgment logic
- Answer directly with Yes/No
- Must base judgment on the model output JSON content (incremental modifications), and verify whether the modifications satisfy the instruction requirements, not speculation

**Output Format (JSON):**
{{
    "answer": "Yes" or "No"
}}

**JSON Format:**
Each modification object contains `original_fragment` (original XML) and `modified_fragment` (modified XML).

**Evaluation Process:**
1. Analyze each modification by comparing `original_fragment` and `modified_fragment`
2. Map instruction requirements to modifications
3. Verify completeness and correctness

**Verification Rules:**
- **Text changes**: Check `value` attribute in `modified_fragment`
- **Color changes**: Check `fillColor`/`strokeColor` in `style` attribute (hex codes like #0000FF or color names)
- **Position/Size**: Check `mxGeometry` coordinates/dimensions
- **Add/Remove**: Check for new elements in `modified_fragment` or empty `modified_fragment` for removals
- **Attributes**: Compare attributes between fragments

**Rules:**
- Analyze all modifications and verify they match the instruction
- Verify completeness (all instruction aspects addressed) and correctness (changes align with instruction)
- If uncertain, answer "No" (conservative strategy)
"""
    
    def _build_xdrfr_prompt_batch(
        self,
        model_output_json: Dict[str, Any],
        instruction: str,
        questions: List[str]
    ) -> str:
        """
        Build XDRFR batch evaluation prompt (evaluate multiple questions at once, based on model_output_json only)
        
        重要：只使用模型输出的增量修改JSON，不传入原始XML，以节省成本。
        只提取问题字段，不提取答案字段，确保答案不会被传入策略模型。
        """
        # 显式构建问题列表，只使用问题字段
        questions_only = [q for q in questions]
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions_only)])
        
        # Convert model_output_json to string format for prompt (no truncation - user requested no truncation)
        # Handle both list and dict formats
        if isinstance(model_output_json, list):
            # If it's a list, it's directly the changes array
            changes = model_output_json
        elif isinstance(model_output_json, dict) and "changes" in model_output_json:
            # If it's a dict with "changes" key
            changes = model_output_json["changes"]
        else:
            # Fallback: treat the whole thing as changes
            changes = model_output_json if isinstance(model_output_json, list) else [model_output_json]
        
        model_output_json_str = json.dumps(changes, ensure_ascii=False, indent=2)
        
        return f"""You are a professional XML modification evaluation expert. Please answer all the following questions with "Yes" or "No" based on the provided model output JSON (containing incremental modifications) and modification instruction.

**Important Note**: The modification instruction uses natural language descriptions (based on rendered images). The model output JSON contains incremental modifications in the format of original_fragment and modified_fragment pairs. You need to understand the natural language instruction, then verify whether the modifications in the JSON satisfy the instruction requirements.

**Model Output JSON (Incremental Modifications):**
```json
{model_output_json_str}
```

**Modification Instruction (Natural Language):**
"{instruction}"

**Question List:**
{questions_text}

**Requirements:**
- Answer each question with only "Yes" or "No", do not output any other content
- Do not output reasons, explanations, evidence, or judgment logic
- Answer each question directly with Yes/No
- Must base judgment on the model output JSON content (incremental modifications), and verify whether the modifications satisfy the instruction requirements, not speculation

**Output Format (JSON):**
{{
    "answers": [
        {{"question": "Complete text of question 1", "answer": "Yes"}},
        {{"question": "Complete text of question 2", "answer": "No"}},
        ...
    ]
}}

**JSON Format:**
Each modification object contains `original_fragment` (original XML) and `modified_fragment` (modified XML).

**Evaluation Process:**
1. Analyze each modification by comparing `original_fragment` and `modified_fragment`
2. Map instruction requirements to modifications
3. Verify completeness and correctness

**Verification Rules:**
- **Text changes**: Check `value` attribute in `modified_fragment`
- **Color changes**: Check `fillColor`/`strokeColor` in `style` attribute (hex codes like #0000FF or color names)
- **Position/Size**: Check `mxGeometry` coordinates/dimensions
- **Add/Remove**: Check for new elements in `modified_fragment` or empty `modified_fragment` for removals
- **Attributes**: Compare attributes between fragments

**Rules:**
- Analyze all modifications and verify they match the instruction
- Verify completeness (all instruction aspects addressed) and correctness (changes align with instruction)
- If uncertain, answer "No" (conservative strategy)
"""
    
    def _parse_batch_answer(self, batch_answer: str, questions: List[str]) -> List[Dict[str, Any]]:
        """
        Parse batch answer containing all questions' answers
        
        Args:
            batch_answer: Model's batch answer (JSON format)
            questions: List of questions
        
        Returns:
            List of result dictionaries for each question
            Format: [{{"question": "Question 1", "answer": "Yes", "is_satisfied": True}}, ...]
        """
        try:
            result = json.loads(batch_answer)
            answers_list = result.get("answers", [])
            
            # Build question to answer mapping
            question_to_answer = {}
            for item in answers_list:
                question_text = item.get("question", "")
                answer_raw = item.get("answer", "")
                # 确保答案是字符串类型（处理模型返回整数或其他类型的情况）
                answer_value = str(answer_raw).strip() if answer_raw is not None else ""
                if question_text and answer_value:
                    question_to_answer[question_text] = answer_value
            
            # Generate results for each question
            per_question_results = []
            for question in questions:
                answer = question_to_answer.get(question, "")
                if not answer:
                    # If cannot find corresponding answer, try fuzzy matching
                    for q_text, a_value in question_to_answer.items():
                        if question in q_text or q_text in question:
                            answer = a_value
                            break
                
                # Normalize answer
                answer_lower = answer.lower().strip()
                if answer_lower in ["yes", "true", "1"]:
                    binary_answer = "Yes"
                    is_satisfied = True
                elif answer_lower in ["no", "false", "0"]:
                    binary_answer = "No"
                    is_satisfied = False
                else:
                    # If cannot parse, default to "No"
                    binary_answer = "No"
                    is_satisfied = False
                
                per_question_results.append({
                    "question": question,
                    "answer": binary_answer,
                    "is_satisfied": is_satisfied
                })
            
            return per_question_results
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse batch answer as JSON: {e}")
            # If parsing fails, return all questions as "No"
            return [
                {
                    "question": question,
                    "answer": "No",
                    "is_satisfied": False
                }
                for question in questions
            ]
        else:
            llm_eval_results = []

        # Step 3: 合并结果（按原始顺序）
        # 先添加 common_questions 的结果
        common_count = len(common_questions or [])
        for i in range(common_count):
            eval_results.append(llm_eval_results[i] if i < len(llm_eval_results) else {
                "question": common_questions[i],
                "answer": "No",
                "is_satisfied": False,
                "verification_method": "llm",
                "error": "LLM evaluation failed"
            })

        # 再添加 decomposed_questions 的结果（按原始顺序）
        decomposed_idx = 0
        llm_idx = common_count
        for question in (decomposed_questions or []):
            # 查找是否已被代码验证
            code_verified = False
            for result in decomposed_eval_results:
                if result["question"] == question:
                    eval_results.append(result)
                    code_verified = True
                    break

            # 如果未被代码验证，从 LLM 结果中获取
            if not code_verified:
                if llm_idx < len(llm_eval_results):
                    eval_results.append(llm_eval_results[llm_idx])
                    llm_idx += 1
                else:
                    eval_results.append({
                        "question": question,
                        "answer": "No",
                        "is_satisfied": False,
                        "verification_method": "llm",
                        "error": "LLM evaluation failed"
                    })

        # Calculate HDRFR score
        satisfied_count = sum(1 for r in eval_results if r["is_satisfied"])
        hdrfr_score = satisfied_count / len(all_questions) if all_questions else 0.0

        logger.info(f"HDRFR Summary: {satisfied_count}/{len(all_questions)} satisfied, "
                   f"Code-verified: {code_verified_count}, LLM-verified: {llm_verified_count}")

        return MetricResult(
            metric_name=self.name,
            score=float(hdrfr_score),
            details={
                "hdrfr_score": float(hdrfr_score),
                "total_questions": len(all_questions),
                "satisfied_count": satisfied_count,
                "common_questions_count": len(common_questions or []),
                "decomposed_questions_count": len(decomposed_questions or []),
                "code_verified_count": code_verified_count,
                "llm_verified_count": llm_verified_count,
                "per_question_results": eval_results
            },
            success=True
        )
    
    def _build_hdrfr_prompt_batch(
        self,
        gemini_image: Path,
        modified_image: Path,
        instruction: str,
        questions: List[str],
        model_output_data: dict = None
    ) -> str:
        """
        Build HDRFR evaluation prompt for batch questions

        Note: 这个 prompt 只用于 LLM 评估美学问题和无法代码验证的问题
              不再依赖 XML code reference，因为精确属性已经通过代码验证了
        """
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])

        return f"""You will see TWO images in the following order:
- FIRST image: Original diagram (Gemini generated)
- SECOND image: Modified diagram (Model generated)

Modification instruction:
"{instruction}"

Please answer ALL the following questions with "Yes" or "No":

{questions_text}

**Output Format (JSON):**
{{
    "answers": [
        {{"question": "Question 1", "answer": "Yes"}},
        {{"question": "Question 2", "answer": "No"}},
        ...
    ]
}}

**Evaluation Guidelines:**

1. **For aesthetic/quality questions** (clarity, balance, spacing, readability, etc.):
   - Answer "Yes" if the diagram looks functional with no SEVERE rendering errors
   - Only answer "No" for CRITICAL issues: overlapping unreadable text, missing elements, broken layout
   - Minor modifications should NOT automatically reduce aesthetic quality
   - If the diagram is nearly identical except for the requested change, aesthetic questions should be "Yes"

2. **For instruction-related questions** (if any remain after code verification):
   - Answer based on careful visual comparison between the two images
   - Look for visible changes that match the instruction
   - Be objective and precise in your assessment

3. **Key principle**: A simple modification (like color change, node addition/removal) should NOT break the overall diagram quality. If only the requested change was made and the diagram still looks functional, aesthetic questions should be "Yes"."""

    def _build_hdrfr_prompt(
        self,
        gemini_image: Path,
        modified_image: Path,
        instruction: str,
        question: str
    ) -> str:
        """Build HDRFR evaluation prompt (simplified version, only output Yes/No)"""
        return f"""You will see TWO images in the following order:
- FIRST image: Original diagram (Gemini generated)
- SECOND image: Modified diagram (Model generated)

Modification instruction:
"{instruction}"

Please carefully compare the FIRST image (original) with the SECOND image (modified), and answer the following question with "Yes" or "No".

Question:
{question}

**Requirements:**
- Only output "Yes" or "No", do not output any other content
- Do not output reasons, explanations, evidence, or judgment logic
- Directly answer with Yes/No

**Output Format (JSON):**
{{
    "answer": "Yes" or "No"
}}

**Important Evaluation Principles:**

1. **For aesthetic/quality questions** (about clarity, balance, harmony, spacing, readability, etc.):
   - Answer "Yes" if the diagram is functional and has NO OBVIOUS rendering errors
   - Only answer "No" if there are SEVERE issues like: text completely overlapping and unreadable, elements missing, connections totally misaligned, or broken layout
   - Minor visual changes (like color modifications) should NOT automatically make aesthetic questions "No"
   - If the original and modified diagrams are nearly identical except for the requested change, aesthetic questions should remain "Yes"

2. **For instruction-specific questions** (about whether specific modifications were made):
   - Answer based on careful visual comparison between the FIRST image (original) and SECOND image (modified)
   - Look for the exact changes mentioned in the instruction
   - For color changes: compare the specific node/element mentioned in the instruction between the two images

3. **Overall guideline**:
   - Be lenient on aesthetic questions unless there are obvious problems
   - Be strict on instruction completion questions
   - Remember: a successful color change or minor modification should NOT break the overall diagram quality"""
    
    def _parse_batch_answer(self, answer: str, questions: List[str]) -> List[Dict]:
        """
        Parse batch answer containing all questions' answers (简化版，只解析答案，不包含证据和逻辑)
        
        Args:
            answer: Model's raw answer (JSON format with answers array)
            questions: List of questions that were asked
        
        Returns:
            List of result dictionaries, one for each question
            Format: [{"question": "...", "answer": "Yes", "is_satisfied": True}, ...]
        """
        eval_results = []
        
        try:
            result = json.loads(answer)
            answers_list = result.get("answers", [])
            
            # 构建问题到答案的映射
            question_to_answer = {}
            for item in answers_list:
                question_text = item.get("question", "")
                answer_raw = item.get("answer", "")
                # 确保答案是字符串类型（处理模型返回整数或其他类型的情况）
                answer_value = str(answer_raw).strip() if answer_raw is not None else ""
                if question_text and answer_value:
                    question_to_answer[question_text] = answer_value
            
            # 为每个问题生成结果
            for question in questions:
                answer_value = question_to_answer.get(question, "")
                if not answer_value:
                    # 如果找不到对应答案，尝试模糊匹配
                    for q_text, a_value in question_to_answer.items():
                        if question in q_text or q_text in question:
                            answer_value = a_value
                            break
                
                # Normalize answer (prioritize English, but support Chinese for backward compatibility)
                answer_lower = answer_value.lower().strip()
                if answer_lower in ["yes", "true", "1", "是"]:
                    binary_answer = "Yes"
                    is_satisfied = True
                elif answer_lower in ["no", "false", "0", "否"]:
                    binary_answer = "No"
                    is_satisfied = False
                else:
                    # If cannot parse, default to "No"
                    binary_answer = "No"
                    is_satisfied = False
                
                eval_results.append({
                    "question": question,
                    "answer": binary_answer,
                    "is_satisfied": is_satisfied
                })
        
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse batch answer as JSON: {e}")
            # 如果解析失败，返回所有问题为"No"
            eval_results = [
                {
                    "question": question,
                    "answer": "No",
                    "is_satisfied": False
                }
                for question in questions
            ]
        
        return eval_results
    
    def _parse_answer(self, answer: str) -> tuple[str, Dict, str]:
        """
        Parse "Yes" or "No" from model answer (简化版，只解析答案，不再解析证据和逻辑)
        
        Args:
            answer: Model's raw answer
        
        Returns:
            Tuple[str, Dict, str]: (binary_answer, evidence, logic)
                - binary_answer: "Yes" or "No"
                - evidence: 空字典（不再存储证据）
                - logic: 空字符串（不再存储逻辑）
        """
        # Try to parse as JSON (new format)
        try:
            result = json.loads(answer)
            # New format: directly get answer field (prioritize English, but support Chinese for backward compatibility)
            answer_value = result.get("answer", "")
            if answer_value:
                answer_value = answer_value.strip().lower()
                if answer_value in ["yes", "true", "1", "是"]:
                    return "Yes", {}, ""
                elif answer_value in ["no", "false", "0", "否"]:
                    return "No", {}, ""
            
            # Compatible with old format: try conclusion field
            conclusion_raw = result.get("conclusion", "")
            # 确保结论是字符串类型（处理模型返回整数或其他类型的情况）
            conclusion = str(conclusion_raw).strip().lower() if conclusion_raw is not None else ""
            if conclusion:
                if conclusion in ["yes", "true", "1", "是"]:
                    return "Yes", {}, ""
                elif conclusion in ["no", "false", "0", "否"]:
                    return "No", {}, ""
        except (json.JSONDecodeError, KeyError):
            # Fallback to old text format parsing
            pass
        
        # Old format: parse from text
        answer_text = answer.strip()
        
        # Check for "Yes" keywords (support both English and Chinese)
        yes_keywords = ["yes", "true", "correct", "satisfies", "meets", "✓", "√", "1", "是", "正确", "满足", "符合"]
        # Check for "No" keywords
        no_keywords = ["no", "false", "incorrect", "does not satisfy", "does not meet", "×", "✗", "0", "否", "错误", "不满足", "不符合"]
        
        # Count keyword occurrences (case-insensitive)
        answer_lower = answer_text.lower()
        yes_count = sum(1 for keyword in yes_keywords if keyword.lower() in answer_lower or keyword in answer_text)
        no_count = sum(1 for keyword in no_keywords if keyword.lower() in answer_lower or keyword in answer_text)
        
        # If clearly contains "Yes" keywords and no "No" keywords
        if yes_count > 0 and no_count == 0:
            return "Yes", {}, ""
        
        # If clearly contains "No" keywords and no "Yes" keywords
        if no_count > 0 and yes_count == 0:
            return "No", {}, ""
        
        # If both exist, judge by count
        if yes_count > no_count:
            return "Yes", {}, ""
        elif no_count > yes_count:
            return "No", {}, ""
        
        # Default case: check answer length, if short and contains "yes" or "no", return directly
        if len(answer_text) <= 5:
            if any(keyword.lower() in answer_lower or keyword in answer_text for keyword in ["yes", "y", "是"]):
                return "Yes", {}, ""
            if any(keyword.lower() in answer_lower or keyword in answer_text for keyword in ["no", "n", "否"]):
                return "No", {}, ""
        
        # If cannot determine, default to "No" (conservative strategy)
        return "No", {}, ""


class XMLEditDistance(BaseMetric):
    """XML 编辑距离 (XED)"""
    
    def __init__(self, distance_type: str = "tree"):
        super().__init__("xml_edit_distance")
        # 默认改为树结构编辑距离；仍保留 character/token 选项用于兼容
        self.distance_type = distance_type  # "character" / "token" / "tree"
    
    def evaluate(
        self,
        gemini_xml_path: Path,
        modified_xml_path: Path,
        **kwargs
    ) -> MetricResult:
        """
        计算 XML 编辑距离
        
        Args:
            gemini_xml_path: Gemini 原始 XML 文件路径
            modified_xml_path: 模型修改后的 XML 文件路径
        """
        try:
            if not gemini_xml_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={"error": f"Gemini XML not found: {gemini_xml_path}"},
                    success=False,
                    error_message=f"Gemini XML not found: {gemini_xml_path}"
                )
            
            if not modified_xml_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={"error": f"Modified XML not found: {modified_xml_path}"},
                    success=False,
                    error_message=f"Modified XML not found: {modified_xml_path}"
                )
            
            gemini_xml = gemini_xml_path.read_text(encoding='utf-8')
            modified_xml = modified_xml_path.read_text(encoding='utf-8')
            
            if self.distance_type == "character":
                edit_distance, max_length = self._character_edit_distance(gemini_xml, modified_xml)
            elif self.distance_type == "token":
                edit_distance, max_length = self._token_edit_distance(gemini_xml, modified_xml)
            elif self.distance_type == "tree":
                edit_distance, max_length = self._tree_edit_distance(gemini_xml, modified_xml)
            else:
                raise ValueError(f"Unknown distance type: {self.distance_type}")
            
            normalized_distance = edit_distance / max_length if max_length > 0 else 0.0
            
            return MetricResult(
                metric_name=self.name,
                score=float(normalized_distance),
                details={
                    "edit_distance": edit_distance,
                    "normalized_distance": float(normalized_distance),
                    "distance_type": self.distance_type,
                    "max_length": max_length
                },
                success=True
            )
        except Exception as e:
            logger.error(f"Error computing XED: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _character_edit_distance(self, s1: str, s2: str) -> tuple[int, int]:
        """字符级编辑距离"""
        edit_distance = self._levenshtein_distance(list(s1), list(s2))
        max_length = max(len(s1), len(s2))
        return edit_distance, max_length
    
    def _token_edit_distance(self, xml1: str, xml2: str) -> tuple[int, int]:
        """Token 级编辑距离"""
        tokens1 = self._tokenize_xml(xml1)
        tokens2 = self._tokenize_xml(xml2)
        edit_distance = self._levenshtein_distance(tokens1, tokens2)
        max_length = max(len(tokens1), len(tokens2))
        return edit_distance, max_length
    
    def _tree_edit_distance(self, xml1: str, xml2: str) -> tuple[int, int]:
        """XML 树结构编辑距离（基于先序遍历序列的 Levenshtein 距离）"""
        try:
            tree1 = ET.fromstring(xml1)
            tree2 = ET.fromstring(xml2)

            def preorder(node: ET.Element) -> list[str]:
                items = [node.tag]
                # 将属性也纳入比较，确保结构+属性差异被捕获
                if node.attrib:
                    items.extend([f"{k}={v}" for k, v in sorted(node.attrib.items())])
                for child in list(node):
                    items.extend(preorder(child))
                return items

            seq1 = preorder(tree1)
            seq2 = preorder(tree2)

            edit_distance = self._levenshtein_distance(seq1, seq2)
            max_length = max(len(seq1), len(seq2))
            return edit_distance, max_length
        except Exception as e:
            logger.warning(f"Failed to parse XML for tree edit distance: {e}, falling back to token distance")
            return self._token_edit_distance(xml1, xml2)
    
    def _levenshtein_distance(self, s1: List, s2: List) -> int:
        """计算 Levenshtein 编辑距离"""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(
                        dp[i-1][j] + 1,      # deletion
                        dp[i][j-1] + 1,      # insertion
                        dp[i-1][j-1] + 1     # substitution
                    )
        
        return dp[m][n]
    
    def _tokenize_xml(self, xml_content: str) -> List[str]:
        """将 XML 内容 tokenize"""
        tokens = []
        
        # 提取标签
        tags = re.findall(r'<[^>]+>', xml_content)
        tokens.extend(tags)
        
        # 提取文本内容
        text_content = re.sub(r'<[^>]+>', ' ', xml_content)
        words = text_content.split()
        tokens.extend(words)
        
        return tokens
