"""
任务一评估指标实现
"""

import logging
import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from scipy.optimize import linear_sum_assignment
from dataclasses import dataclass
import time

from eval.base import BaseMetric, MetricResult
from src.llm.client import LLMClient
from src.renderer.drawio_renderer import DrawioRenderer

logger = logging.getLogger(__name__)


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


@dataclass
class Element:
    """图表元素数据结构"""
    id: str
    type: str  # "node" | "edge" | "text" | "unknown"
    bbox: Dict[str, int]  # {"x": int, "y": int, "width": int, "height": int}
    confidence: float = 1.0


class ExecutionSuccessRate(BaseMetric):
    """执行成功率"""
    
    def __init__(self, renderer: Optional[DrawioRenderer] = None):
        super().__init__("execution_success_rate")
        self.renderer = renderer
    
    def evaluate(
        self,
        xml_path: Path,
        rendered_path: Optional[Path] = None,
        **kwargs
    ) -> MetricResult:
        """
        评估XML是否能够成功执行
        
        Args:
            xml_path: XML文件路径
            rendered_path: 渲染图路径（如果存在，说明渲染成功）
        
        Note:
            这个指标应该始终返回 success=True，除非评估过程本身出错。
            如果XML不存在或渲染失败，应该返回 score=0.0 但 success=True。
        """
        try:
            # 检查XML文件是否存在
            if not xml_path.exists():
                # XML不存在：执行失败，但评估本身是成功的
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={
                        "execution_success": False,
                        "render_success": False,
                        "xml_valid": False,
                        "error": "XML file not found"
                    },
                    success=True  # 评估本身成功，只是执行失败了
                )
            
            # 检查渲染图是否存在（如果提供了路径）
            execution_success = True
            render_success = False
            error_message = None
            xml_valid = True
            
            if rendered_path:
                # 如果提供了渲染图路径，直接检查文件是否存在
                render_success = rendered_path.exists()
                execution_success = render_success
            else:
                # 如果没有提供渲染图路径，尝试渲染
                if self.renderer:
                    try:
                        from src.core.models import DiagramXML
                        xml_content = xml_path.read_text(encoding='utf-8')
                        diagram = DiagramXML(content=xml_content)
                        # 尝试渲染（使用临时文件）
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            tmp_path = Path(tmp.name)
                            self.renderer.render(diagram, tmp_path)
                            render_success = tmp_path.exists()
                            execution_success = render_success
                            tmp_path.unlink()  # 清理临时文件
                    except Exception as e:
                        # 渲染失败：执行失败，但评估本身是成功的
                        error_message = str(e)
                        execution_success = False
                        render_success = False
                else:
                    # 没有渲染器，无法评估
                    execution_success = False
                    render_success = False
                    error_message = "Renderer not available"
            
            # 评估成功，返回结果（无论执行是否成功）
            return MetricResult(
                metric_name=self.name,
                score=1.0 if execution_success else 0.0,
                details={
                    "execution_success": execution_success,
                    "render_success": render_success,
                    "xml_valid": xml_valid,
                    "error_message": error_message
                },
                success=True  # 评估本身总是成功的
            )
        except Exception as e:
            # 只有在评估过程本身出错时才返回 success=False
            # 这种情况应该很少发生，比如文件系统错误、内存不足等
            return MetricResult(
                metric_name=self.name,
                score=None,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )


class XMLTokenCount(BaseMetric):
    """XML Token数量"""
    
    def __init__(self, tokenizer_name: str = "cl100k_base"):
        super().__init__("xml_token_count")
        self.tokenizer_name = tokenizer_name
    
    def evaluate(self, xml_path: Path, **kwargs) -> MetricResult:
        """统计XML Token数量"""
        try:
            if not xml_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=None,
                    details={"error": "XML file not found"},
                    success=False,
                    error_message="XML file not found"
                )
            
            xml_content = xml_path.read_text(encoding='utf-8')
            token_count, tokenizer_used = count_tokens_offline(xml_content, self.tokenizer_name)
            
            return MetricResult(
                metric_name=self.name,
                score=float(token_count),  # Token数量作为分数
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
                score=None,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )


class StyleConsistencyScore(BaseMetric):
    """风格一致性打分"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("style_consistency_score")
        self.llm_client = llm_client
        # Keep original default, but allow override for rebuttal re-evaluation.
        self.judge_model = os.getenv("TASK1_JUDGE_MODEL", "gemini-3-pro-preview")
    
    def evaluate(
        self,
        original_image_path: Path,
        generated_image_path: Path,
        execution_success: bool = True,
        **kwargs
    ) -> MetricResult:
        """使用LLM评估风格一致性"""
        # 如果执行失败，直接返回 0.0
        if not execution_success:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "Execution failed"},
                success=True
            )
        
        # 检查渲染图是否存在
        if not generated_image_path.exists():
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "Generated image not found"},
                success=True
            )
        
        if not self.llm_client:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "LLM client not provided"},
                success=False,
                error_message="LLM client not provided"
            )
        
        try:
            prompt = self._get_prompt(original_image_path, generated_image_path)
            # 传入两张图片（原图和生成图）
            response, usage_stats = self.llm_client._call_vision_api(
                prompt=prompt,
                image_input=[original_image_path, generated_image_path],
                provider="custom",
                model=self.judge_model,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            # 解析 JSON 响应
            try:
                result = json.loads(response)
                score = result.get("final_score", 0.0)
                
                # 如果 final_score 不存在，尝试从 dimension_scores 计算
                if score == 0.0 and "analysis" in result:
                    dim_scores = result["analysis"].get("dimension_scores", {})
                    if dim_scores:
                        avg_score = (
                            dim_scores.get("visual_style_consistency", 0) +
                            dim_scores.get("layout_consistency", 0) +
                            dim_scores.get("aesthetic_quality", 0)
                        ) / 3.0
                        score = avg_score / 10.0  # 归一化到 0-1
                
                # 确保得分在 0-1 范围内
                score = max(0.0, min(1.0, score))
                
                logger.info(f"SCS evaluation: dimension_scores={result.get('analysis', {}).get('dimension_scores', {})}, final_score={score}")
                
                # 转换为相对路径（相对于包含task1_benchmark的目录）
                original_image_rel = self._get_relative_path(original_image_path)
                generated_image_rel = self._get_relative_path(generated_image_path)
                
                return MetricResult(
                    metric_name=self.name,
                    score=float(score),
                    details={
                        "style_consistency_score": float(score),
                        "original_image": original_image_rel,
                        "generated_image": generated_image_rel,
                        "analysis": result.get("analysis", {}),
                        "dimension_scores": result.get("analysis", {}).get("dimension_scores", {})
                    },
                    success=True
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse SCS response as JSON: {e}, trying fallback parsing")
                # Fallback to simple float parsing
                score = self._parse_float_from_response(response)
                score = max(0.0, min(1.0, score))
                
                # 转换为相对路径（相对于包含task1_benchmark的目录）
                original_image_rel = self._get_relative_path(original_image_path)
                generated_image_rel = self._get_relative_path(generated_image_path)
                
                return MetricResult(
                    metric_name=self.name,
                    score=float(score),
                    details={
                        "style_consistency_score": float(score),
                        "original_image": original_image_rel,
                        "generated_image": generated_image_rel,
                        "warning": "JSON parsing failed, used fallback parsing"
                    },
                    success=True
                )
        except Exception as e:
            logger.error(f"Error in style consistency evaluation: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=None,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _parse_float_from_response(self, response: str) -> float:
        """Parse float from response"""
        import re
        # 尝试提取数字
        numbers = re.findall(r'\d+\.?\d*', response)
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                pass
        # 如果找不到数字，返回 0.0
        return 0.0
    
    def _get_prompt(self, original_path: Path, generated_path: Path) -> str:
        """Generate evaluation prompt (optimized version with chain-of-thought and dimension scoring)"""
        return f"""You are a professional diagram design reviewer. Please compare the "original diagram" and "generated diagram" and conduct a systematic evaluation following these steps:

Original diagram:
[Image: {original_path}]

Generated diagram:
[Image: {generated_path}]

**Evaluation Steps:**

**Step 1: Attribute Extraction**
Please carefully analyze the original diagram and extract the following key attributes:
- Color scheme: List the main colors' hexadecimal values or color family names (e.g., "blue family", "warm tones")
- Font style: Font weight (thin/medium/bold), size (small/medium/large), font family (if any)
- Layout structure: Overall structure type (tree/ring/linear/grid/free layout)
- Visual elements: Node shapes (circle/rectangle/diamond, etc.), line styles (solid/dashed/thickness)

**Step 2: Difference Comparison**
Check the deviation of the above attributes in the generated diagram one by one:
- Is the color scheme consistent? If there are differences, describe the specific differences
- Does the font style match?
- Is the layout structure the same? Are element positions and spacing relationships consistent?
- Are visual element styles consistent?

**Step 3: Dimension Scoring (0-10 scale)**
Please score the following three dimensions separately (0-10 points, keep one decimal place):
1. Visual style consistency (color, line thickness, node style): ___
2. Layout structure consistency (element positions, spacing, spatial relationships): ___
3. Aesthetic quality (alignment, visual balance, overall beauty): ___

**Step 4: Final Score Calculation**
- Calculate the average of the three dimension scores
- Divide the average by 10 to normalize to 0-1
- Example: Dimension scores [8.5, 7.0, 9.0], average = 8.17, final score = 0.817

**Output Format (JSON):**
{{
    "analysis": {{
        "original_attributes": {{
            "color_scheme": "...",
            "font_style": "...",
            "layout_structure": "...",
            "visual_elements": "..."
        }},
        "differences": [
            "Difference description 1",
            "Difference description 2"
        ],
        "dimension_scores": {{
            "visual_style_consistency": 8.5,
            "layout_consistency": 7.0,
            "aesthetic_quality": 9.0
        }},
        "average_score": 8.17
    }},
    "final_score": 0.817
}}

**Important Notes:**
- Please strictly follow the scoring criteria and avoid directly giving high scores (0.85+)
- You must complete attribute extraction and difference comparison before giving dimension scores
- If the generated diagram has obvious visual errors (such as element overlap, text misalignment), points should be deducted in the corresponding dimension
- The final score must be calculated based on the average of dimension scores, not estimated directly"""
    
    def _get_relative_path(self, path: Path) -> str:
        """
        将绝对路径转换为相对路径（相对于包含task1_benchmark的目录）
        
        Args:
            path: 绝对路径
            
        Returns:
            相对路径字符串
        """
        path_str = str(path)
        
        # 查找task1_benchmark在路径中的位置
        benchmark_marker = "task1_benchmark"
        if benchmark_marker in path_str:
            # 找到task1_benchmark目录
            parts = Path(path_str).parts
            try:
                benchmark_idx = parts.index(benchmark_marker)
                # 基准目录是task1_benchmark的父目录
                base_parts = parts[:benchmark_idx]
                # 相对路径从task1_benchmark开始
                rel_parts = parts[benchmark_idx:]
                return str(Path(*rel_parts))
            except ValueError:
                pass
        
        # 如果找不到task1_benchmark，返回原始路径
        return path_str
    


class StructuralFidelity(BaseMetric):
    """结构保真度（基于IoU + 二分图匹配）"""
    
    def __init__(self, detection_model: Optional[Any] = None):
        super().__init__("structural_fidelity")
        self.detection_model = detection_model
        if detection_model is None:
            try:
                from ultralytics import YOLO

                self.detection_model = YOLO('yolov8n.pt')
                logger.info("Loaded YOLOv8 model for structural fidelity")
            except Exception as e:
                logger.warning(f"Failed to load YOLOv8 model: {e}")
                self.detection_model = None
    
    def evaluate(
        self,
        original_image_path: Path,
        generated_rendered_path: Path,
        generated_xml_path: Optional[Path] = None,
        **kwargs
    ) -> MetricResult:
        """评估结构保真度"""
        if not self.detection_model:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "Detection model not available"},
                success=False,
                error_message="Detection model not available"
            )
        
        try:
            # 提取边界框
            reference_elements = self._extract_bboxes(original_image_path)
            generated_elements = self._extract_bboxes(generated_rendered_path)
            
            if not reference_elements or not generated_elements:
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={
                        "error": "Failed to extract elements",
                        "reference_count": len(reference_elements),
                        "generated_count": len(generated_elements)
                    },
                    success=False,
                    error_message="Failed to extract elements"
                )
            
            # 二分图匹配
            matched_pairs = self._bipartite_matching(reference_elements, generated_elements)
            
            # 计算IoU
            iou_scores = []
            element_matches = []
            for ref_elem, gen_elem in matched_pairs:
                iou = self._calculate_iou(ref_elem.bbox, gen_elem.bbox)
                iou_scores.append(iou)
                element_matches.append({
                    "reference_element_id": ref_elem.id,
                    "generated_element_id": gen_elem.id,
                    "iou": float(iou),
                    "element_type": ref_elem.type,
                    "bbox_reference": ref_elem.bbox,
                    "bbox_generated": gen_elem.bbox
                })
            
            mean_iou = float(np.mean(iou_scores)) if iou_scores else 0.0
            
            return MetricResult(
                metric_name=self.name,
                score=mean_iou,
                details={
                    "mean_iou": mean_iou,
                    "matched_elements_count": len(matched_pairs),
                    "total_reference_elements": len(reference_elements),
                    "total_generated_elements": len(generated_elements),
                    "element_matches": element_matches
                },
                success=True
            )
        except Exception as e:
            logger.error(f"Error in structural fidelity evaluation: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=None,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _extract_bboxes(self, image_path: Path) -> List[Element]:
        """从图片中提取元素边界框"""
        if not image_path.exists():
            return []
        
        try:
            results = self.detection_model(str(image_path), conf=0.25)
            elements = []
            
            for result in results:
                boxes = result.boxes
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    bbox = {
                        "x": int(x1),
                        "y": int(y1),
                        "width": int(x2 - x1),
                        "height": int(y2 - y1)
                    }
                    
                    element_type = self._infer_element_type(bbox)
                    
                    elements.append(Element(
                        id=f"detected_{i}",
                        type=element_type,
                        bbox=bbox,
                        confidence=confidence
                    ))
            
            return elements
        except Exception as e:
            logger.error(f"Error extracting bboxes from {image_path}: {e}")
            return []
    
    def _infer_element_type(self, bbox: Dict[str, int]) -> str:
        """根据边界框形状推断元素类型"""
        width = bbox['width']
        height = bbox['height']
        aspect_ratio = width / height if height > 0 else 1.0
        
        if aspect_ratio > 5 or aspect_ratio < 0.2:
            return "edge"
        if width > 20 and height > 20:
            return "node"
        if width < 50 and height < 50:
            return "text"
        return "unknown"
    
    def _calculate_iou(self, bbox1: Dict[str, int], bbox2: Dict[str, int]) -> float:
        """计算两个边界框的IoU"""
        x1 = max(bbox1["x"], bbox2["x"])
        y1 = max(bbox1["y"], bbox2["y"])
        x2 = min(bbox1["x"] + bbox1["width"], bbox2["x"] + bbox2["width"])
        y2 = min(bbox1["y"] + bbox1["height"], bbox2["y"] + bbox2["height"])
        
        if x2 <= x1 or y2 <= y1:
            intersection = 0
        else:
            intersection = (x2 - x1) * (y2 - y1)
        
        area1 = bbox1["width"] * bbox1["height"]
        area2 = bbox2["width"] * bbox2["height"]
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_matching_cost(self, ref_elem: Element, gen_elem: Element, max_distance: float = 200.0) -> float:
        """计算匹配成本"""
        if ref_elem.type != gen_elem.type:
            return float('inf')
        
        ref_center_x = ref_elem.bbox["x"] + ref_elem.bbox["width"] / 2
        ref_center_y = ref_elem.bbox["y"] + ref_elem.bbox["height"] / 2
        gen_center_x = gen_elem.bbox["x"] + gen_elem.bbox["width"] / 2
        gen_center_y = gen_elem.bbox["y"] + gen_elem.bbox["height"] / 2
        
        distance = np.sqrt(
            (ref_center_x - gen_center_x) ** 2 + 
            (ref_center_y - gen_center_y) ** 2
        )
        
        return min(distance / max_distance, 1.0)
    
    def _bipartite_matching(self, reference_elements: List[Element], generated_elements: List[Element]) -> List[tuple]:
        """二分图匹配"""
        if not reference_elements or not generated_elements:
            return []
        
        n_ref = len(reference_elements)
        n_gen = len(generated_elements)
        cost_matrix = np.zeros((n_ref, n_gen))
        
        for i, ref_elem in enumerate(reference_elements):
            for j, gen_elem in enumerate(generated_elements):
                cost_matrix[i, j] = self._calculate_matching_cost(ref_elem, gen_elem)
        
        row_indices, col_indices = linear_sum_assignment(cost_matrix)
        
        max_cost_threshold = 0.5
        matched_pairs = []
        for i, j in zip(row_indices, col_indices):
            if cost_matrix[i, j] < max_cost_threshold:
                matched_pairs.append((reference_elements[i], generated_elements[j]))
        
        return matched_pairs


class ElementRecallRate(BaseMetric):
    """元素召回率"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("element_recall_rate")
        self.llm_client = llm_client
    
    def evaluate(
        self,
        original_description_path: Path,
        rendered_image_path: Path,
        description_prompt_template: Optional[str] = None,
        **kwargs
    ) -> MetricResult:
        """评估元素召回率"""
        if not self.llm_client:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "LLM client not provided"},
                success=False,
                error_message="LLM client not provided"
            )
        
        try:
            # 检查文件是否存在
            if not original_description_path.exists():
                return MetricResult(
                    metric_name=self.name,
                    score=0.0,
                    details={
                        "error": f"Reference description file not found: {original_description_path}",
                        "hint": "Expected to find model_gemini/llm_description.txt as reference"
                    },
                    success=False,
                    error_message=f"Reference description file not found: {original_description_path}"
                )
            
            # 读取原图描述
            original_description = original_description_path.read_text(encoding='utf-8')
            
            # 生成渲染图描述
            rendered_description = self._generate_description(rendered_image_path, description_prompt_template)
            
            # 提取元素
            original_elements = self._extract_elements(original_description)
            rendered_elements = self._extract_elements(rendered_description)
            
            # 匹配元素
            matched, missing, extra = self._match_elements(original_elements, rendered_elements)
            
            recall_rate = len(matched) / len(original_elements) if original_elements else 0.0
            
            return MetricResult(
                metric_name=self.name,
                score=recall_rate,
                details={
                    "original_elements_count": len(original_elements),
                    "matched_elements_count": len(matched),
                    "recall_rate": recall_rate,
                    "missing_elements": missing,
                    "extra_elements": extra
                },
                success=True
            )
        except Exception as e:
            logger.error(f"Error in element recall evaluation: {e}", exc_info=True)
            return MetricResult(
                metric_name=self.name,
                score=None,
                details={"error": str(e)},
                success=False,
                error_message=str(e)
            )
    
    def _generate_description(self, image_path: Path, prompt_template: Optional[str] = None) -> str:
        """生成图片描述"""
        if prompt_template is None:
            prompt_template = """Please provide a detailed description of all elements in this diagram, including nodes, connecting lines, text labels, etc."""
        
        response, _ = self.llm_client._call_vision_api(
            prompt=prompt_template,
            image_input=image_path,
            provider="custom",
            model="gemini-3-pro-preview",
            temperature=0.3
        )
        return response
    
    def _extract_elements(self, description: str) -> List[Dict[str, Any]]:
        """从描述中提取元素列表"""
        # 简单的元素提取（可以根据需要改进）
        elements = []
        lines = description.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 简单的启发式规则：包含"节点"、"连接"、"线"等关键词
            if any(keyword in line for keyword in ['节点', '连接', '线', '元素', '矩形', '圆形']):
                elements.append({"text": line, "type": "unknown"})
        return elements
    
    def _match_elements(self, original: List[Dict], rendered: List[Dict]) -> tuple:
        """匹配元素"""
        matched = []
        missing = []
        extra = rendered.copy()
        
        for orig_elem in original:
            found = False
            for i, rend_elem in enumerate(extra):
                # 简单的文本相似度匹配
                if self._similar(orig_elem.get("text", ""), rend_elem.get("text", "")):
                    matched.append(orig_elem)
                    extra.pop(i)
                    found = True
                    break
            if not found:
                missing.append(orig_elem)
        
        return matched, missing, extra
    
    def _similar(self, text1: str, text2: str, threshold: float = 0.5) -> bool:
        """简单的文本相似度判断"""
        # 使用简单的关键词匹配
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return False
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        similarity = intersection / union if union > 0 else 0.0
        return similarity >= threshold


class CodeVQA(BaseMetric):
    """CodeVQA 符号保真度评估"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__("codevqa")
        self.llm_client = llm_client
        # Keep original default, but allow override for rebuttal re-evaluation.
        self.policy_model = os.getenv("TASK1_JUDGE_MODEL", "gemini-3-pro-preview")
    
    def evaluate(
        self,
        generated_xml: str,
        qa_pairs: List[Dict[str, str]],
        execution_success: bool = True,
        **kwargs
    ) -> MetricResult:
        """
        评估 CodeVQA 符号保真度
        
        Args:
            generated_xml: 模型生成的 XML 代码（字符串）
            qa_pairs: QA 对列表（应包含 3 个不同类型的 QA 对）
            execution_success: XML 是否执行成功
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
        # 因为现在输入的是模型生成的XML，可以直接基于XML进行评估
        
        # 检查 XML 是否存在
        if not generated_xml or not generated_xml.strip():
            return MetricResult(
                metric_name=self.name,
                score=None,
                details={
                    "total_questions": len(qa_pairs) if qa_pairs else 0,
                    "correct_answers": 0,
                    "per_question_results": [
                        {
                            "question": qa.get("question", ""),
                            "question_type": qa.get("question_type", "unknown"),
                            "ground_truth": qa.get("answer", ""),
                            "generated_answer": "N/A (XML not found or empty)",
                            "is_correct": False
                        }
                        for qa in (qa_pairs or [])
                    ]
                },
                success=False,
                error_message="XML not found or empty"
            )
        
        # Use project-default judge model unless overridden by TASK1_JUDGE_MODEL
        policy_model = self.policy_model
        
        results = []
        correct_count = 0
        
        # 优化：批量处理所有问题，减少API调用次数
        if qa_pairs and len(qa_pairs) > 0:
            try:
                # 批量查询所有问题
                sample_info = kwargs.get('sample_info', '')
                batch_answers = self._query_policy_model_batch(
                    generated_xml=generated_xml,
                    qa_pairs=qa_pairs,
                    model=policy_model,
                    sample_info=sample_info
                )
                
                # 检查批量查询是否成功（至少有一个答案）
                if not batch_answers or len(batch_answers) == 0 or not any(batch_answers):
                    # 批量查询失败，直接抛出异常，不进行单个查询回退
                    raise Exception(f"Batch query failed: no answers returned")
                
                # 处理每个问题的答案
                for i, qa in enumerate(qa_pairs):
                    question = qa.get("question", "")
                    ground_truth = qa.get("answer", "")
                    question_type = qa.get("question_type", "open")
                    
                    # 获取对应的答案
                    if i < len(batch_answers) and batch_answers[i]:
                        generated_answer = batch_answers[i]
                    else:
                        # 批量查询结果不完整，直接抛出异常，不进行单个查询回退
                        raise Exception(f"Batch query result incomplete: missing answer for question {i+1}")
                    
                    # 评估答案正确性
                    is_correct = self._evaluate_answer_correctness(
                        generated_answer=generated_answer,
                        ground_truth=ground_truth,
                        question_type=question_type
                    )
                    
                    if is_correct:
                        correct_count += 1
                    
                    results.append({
                        "question": question,
                        "question_type": question_type,
                        "ground_truth": ground_truth,
                        "generated_answer": generated_answer,
                        "is_correct": is_correct
                    })
            except Exception as e:
                # 批量查询失败，直接抛出异常，不进行单个查询回退
                logger.error(f"Error in batch evaluation: {e}, will save as None for retry")
                raise  # 重新抛出异常，让evaluator捕获并保存为None
        
        accuracy = correct_count / len(qa_pairs) if qa_pairs else 0.0
        
        return MetricResult(
            metric_name=self.name,
            score=accuracy,
            details={
                "total_questions": len(qa_pairs) if qa_pairs else 0,
                "correct_answers": correct_count,
                "per_question_results": results
            },
            success=True
        )
    
    def _query_policy_model_batch(
        self,
        generated_xml: str,
        qa_pairs: List[Dict[str, str]],
        model: str = "gemini-3-pro-preview",
        sample_info: str = ""
    ) -> List[str]:
        """
        批量使用策略模型根据 XML 回答多个问题（优化：减少API调用次数）
        
        实现方案1：基于处理时间的预防
        - 设置90秒客户端超时（在Cloudflare超时前主动取消）
        - 监控处理时间，超过80秒标记为高风险
        """
        # 重要：只提取问题字段，不提取答案字段，确保答案不会被传入策略模型
        # 显式构建问题列表，只使用 'question' 字段
        questions_only = [qa.get('question', '') for qa in qa_pairs]
        
        # 构建批量问题的prompt（只包含问题，不包含答案）
        questions_text = "\n".join([
            f"Q{i+1}: {question}" 
            for i, question in enumerate(questions_only)
        ])
        
        prompt = f"""You are a professional diagram analysis expert. Please carefully analyze the following Draw.io XML code and answer ALL the questions below based on the XML content.

**Generated XML Code:**
```xml
{generated_xml}
```

**Questions:**
{questions_text}

**Instructions:**
- Analyze the XML code structure, elements, attributes, and content
- For counting questions: Count specific elements or attributes in the XML
- For identification questions: Find specific text values, IDs, or attributes in the XML
- For relationship questions: Analyze connections, hierarchy, or relationships between elements in the XML
- Answer each question based solely on the XML code provided
- Do not make assumptions beyond what is in the XML

**Output Format (JSON):**
Please provide answers in the following JSON format (one answer per question):
{{
    "Q1": "<answer to question 1>",
    "Q2": "<answer to question 2>",
    ...
}}

**Important:** 
- Answer each question directly without additional explanations
- Use the exact question numbers (Q1, Q2, Q3, etc.) as keys
- Provide concise answers only
- Base your answers strictly on the XML code content"""
        
        start_time = time.time()
        
        try:
            # 使用文本 API，不传入图像
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
            # 尝试从参数获取样本信息（如果可用）
            if sample_info:
                logger.info(f"{sample_info} Starting CodeVQA batch query (XML size: {len(generated_xml):,} chars, Questions: {len(qa_pairs)})")
            else:
                logger.info(f"Starting CodeVQA batch query (XML size: {len(generated_xml):,} chars, Questions: {len(qa_pairs)})")
            
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
            
            response_text = response.choices[0].message.content
            
            # 记录实际返回的内容（前500字符）
            response_preview = response_text[:500] if len(response_text) > 500 else response_text
            logger.info(f"Policy model response preview (first 500 chars): {response_preview}")
            
            # 移除markdown代码块包装
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:].strip()
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:].strip()
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3].strip()
            
            # 解析JSON响应
            try:
                parsed = json.loads(cleaned_response)
                answers: List[str] = []
                # 部分 API/模型会返回 JSON 数组而非 {"Q1":...,"Q2":...}，直接 .get 会报错
                if isinstance(parsed, list):
                    for i in range(len(qa_pairs)):
                        if i >= len(parsed):
                            answers.append("")
                            continue
                        item = parsed[i]
                        if isinstance(item, dict):
                            key = f"Q{i + 1}"
                            v = item.get(key)
                            if v is None:
                                v = item.get("answer")
                            if v is None and len(item) == 1:
                                v = next(iter(item.values()))
                            answers.append("" if v is None else str(v).strip())
                        else:
                            answers.append("" if item is None else str(item).strip())
                    return answers
                if not isinstance(parsed, dict):
                    logger.warning(
                        f"Batch response JSON is not dict/list (type={type(parsed).__name__}); trying fallback"
                    )
                    return self._parse_batch_answers_from_text(response_text, len(qa_pairs))
                answers_dict = parsed
                for i in range(len(qa_pairs)):
                    key = f"Q{i+1}"
                    answer_value = answers_dict.get(key, "")
                    # 确保答案是字符串类型（处理模型返回整数或其他类型的情况）
                    if answer_value is None:
                        answer = ""
                    else:
                        answer = str(answer_value).strip()
                    answers.append(answer)
                return answers
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse batch response as JSON: {e}, trying fallback parsing")
                logger.warning(f"Response content (first 500 chars): {response_preview}")
                # 回退：尝试从文本中提取答案
                return self._parse_batch_answers_from_text(response_text, len(qa_pairs))
        except TimeoutError as e:
            # 服务器超时（OpenAI SDK的timeout参数触发，通常是1200秒）
            elapsed = time.time() - start_time
            logger.error(f"Server timeout after {elapsed:.1f}s when querying policy model in batch: {e}")
            logger.error("This likely indicates server is slow or overloaded. Please retry later.")
            return []
        except Exception as e:
            error_str = str(e).lower()
            elapsed = time.time() - start_time
            
            # 检测 524 错误并记录警告
            if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                logger.error(f"HTTP 524 Cloudflare timeout error when querying policy model in batch (after {elapsed:.1f}s): {e}")
                logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request, which could result in billing.")
            elif 'timeout' in error_str or 'timed out' in error_str:
                logger.error(f"Timeout error when querying policy model in batch (after {elapsed:.1f}s): {e}")
                logger.error("Request may have been cancelled or server timed out. Check server status before retrying.")
            else:
                logger.error(f"Error querying policy model in batch (after {elapsed:.1f}s): {e}")
            return []
    
    def _parse_batch_answers_from_text(self, text: str, num_questions: int) -> List[str]:
        """从文本响应中解析批量答案（回退方法，使用正则表达式）"""
        if not text or not text.strip():
            return [""] * num_questions
        
        answers = []
        text_clean = text.strip()
        
        for i in range(num_questions):
            key = f"Q{i+1}"
            answer = ""
            
            # 方法1: 使用正则表达式提取JSON格式的键值对
            # 匹配 "Q1": "answer" 或 "Q1": 'answer' 或 "Q1": answer
            pattern1 = rf'"{key}"\s*:\s*"([^"]*)"'  # "Q1": "answer"
            pattern2 = rf'"{key}"\s*:\s*\'([^\']*)\''  # "Q1": 'answer'
            pattern3 = rf'"{key}"\s*:\s*([^,}}\n]+)'  # "Q1": answer (无引号)
            
            match = re.search(pattern1, text_clean) or re.search(pattern2, text_clean) or re.search(pattern3, text_clean)
            if match:
                answer = match.group(1).strip().strip('"').strip("'")
                answers.append(answer)
                continue
            
            # 方法2: 从行中提取（格式如 Q1: answer）
            lines = text_clean.split('\n')
            for line in lines:
                line_lower = line.lower()
                if (key.lower() in line_lower or 
                    f"question {i+1}" in line_lower or 
                    f"q{i+1}" in line_lower):
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            answer = parts[1].strip().strip('"').strip("'")
                    else:
                        answer = line.strip().strip('"').strip("'")
                    break
            
            answers.append(answer if answer else "")
        
        return answers
    
    def _query_policy_model(
        self,
        generated_xml: str,
        question: str,
        model: str = "gemini-3-pro-preview"
    ) -> str:
        """
        使用策略模型根据 XML 回答问题（单个问题，用于回退）
        
        重要：只传入问题和XML，不传入答案。答案仅在后续评估时用于比较。
        """
        prompt = f"""You are a professional diagram analysis expert. Please carefully analyze the following Draw.io XML code and answer the question based on the XML content.

**Generated XML Code:**
```xml
{generated_xml}
```

**Question:**
{question}

**Instructions:**
- Analyze the XML code structure, elements, attributes, and content
- For counting questions: Count specific elements or attributes in the XML
- For identification questions: Find specific text values, IDs, or attributes in the XML
- For relationship questions: Analyze connections, hierarchy, or relationships between elements in the XML
- Answer the question based solely on the XML code provided
- Do not make assumptions beyond what is in the XML

Please provide the answer directly without additional explanations."""
        
        try:
            # 使用文本 API，不传入图像
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
                temperature=0.0
            )
            
            response_text = response.choices[0].message.content
            return response_text.strip()
        except Exception as e:
            error_str = str(e).lower()
            # 检测 524 错误并记录警告
            if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                logger.error(f"HTTP 524 Cloudflare timeout error when querying policy model: {e}")
                logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request, which could result in billing.")
            else:
                logger.error(f"Error querying policy model: {e}")
            return ""
    
    def _evaluate_answer_correctness(
        self,
        generated_answer: str,
        ground_truth: str,
        question_type: str
    ) -> bool:
        """
        评估答案是否正确，支持语义匹配
        
        评估策略（按优先级）：
        1. 精确匹配（标准化后）
        2. 包含匹配（一个答案包含另一个）
        3. 实体集合匹配（提取所有实体，忽略连接词和顺序）
        4. 实体部分匹配（处理连字符、空格等格式差异）
        """
        import re
        
        # 连接词列表（在关系类问题中应该被忽略）
        CONJUNCTIONS = {'and', 'or', '&', 'and/or', 'plus', 'with', ',', '，'}
        
        # 标准化答案（去除标点、转换为小写、规范化空格）
        def normalize_answer(answer: str) -> str:
            answer = answer.strip()
            answer = answer.lower()
            # 去除标点符号，但保留空格
            answer = re.sub(r'[^\w\s]', '', answer)
            # 合并多个空格为单个空格
            answer = re.sub(r'\s+', ' ', answer)
            return answer
        
        # 提取实体列表（通过连接词分割）
        def extract_entities(text: str) -> list:
            """
            从文本中提取实体列表
            例如："spec-aware checker and spec-aware generator" 
            -> ["spec-aware checker", "spec-aware generator"]
            """
            normalized = normalize_answer(text)
            # 使用连接词分割
            # 先替换常见分隔符为统一标记
            for conj in CONJUNCTIONS:
                normalized = normalized.replace(conj, '|')
            # 分割并清理
            entities = [e.strip() for e in normalized.split('|') if e.strip()]
            return entities
        
        normalized_generated = normalize_answer(generated_answer)
        normalized_ground_truth = normalize_answer(ground_truth)
        
        # 对于计数类问题，直接比较数字
        if question_type == "counting":
            # 提取数字
            gen_numbers = re.findall(r'\d+', normalized_generated)
            gt_numbers = re.findall(r'\d+', normalized_ground_truth)
            
            if gen_numbers and gt_numbers:
                return gen_numbers[0] == gt_numbers[0]
            # 如果没有数字，进行字符串匹配
            return normalized_generated == normalized_ground_truth
        
        # 对于识别类和关系类问题，进行语义匹配
        elif question_type in ["identification", "relationship"]:
            # 1. 精确匹配（标准化后）
            if normalized_generated == normalized_ground_truth:
                return True
            
            # 2. 包含匹配（仅当标准答案是单个实体时使用，避免部分匹配问题）
            # 先提取实体，如果只有一个实体，可以使用包含匹配
            gt_entities = extract_entities(ground_truth)
            gen_entities = extract_entities(generated_answer)
            
            # 如果标准答案只有一个实体，可以使用包含匹配
            if len(gt_entities) == 1:
                if normalized_ground_truth in normalized_generated or normalized_generated in normalized_ground_truth:
                    return True
            # 如果标准答案包含多个实体，必须进行实体级别的匹配，不能简单使用包含匹配
            
            # 3. 实体集合匹配（提取实体，忽略连接词和顺序）
            
            # 标准化实体（去除连字符、空格等，只保留字母数字）
            def normalize_entity(entity: str) -> str:
                # 去除所有非字母数字字符，只保留内容
                return re.sub(r'[^\w]', '', entity.lower())
            
            gt_entities_normalized = {normalize_entity(e) for e in gt_entities if e}
            gen_entities_normalized = {normalize_entity(e) for e in gen_entities if e}
            
            # 如果实体集合完全相等（允许顺序不同），认为正确
            # 注意：这里要求完全相等，确保语义一致性
            # 例如："节点A和节点B" 匹配 "节点A、节点B" ✓
            # 但 "节点A和节点B" 不匹配 "节点A、节点B和节点C" ✗
            if gt_entities_normalized == gen_entities_normalized:
                return True
            
            # 4. 实体部分匹配（处理格式差异，如 "spec-aware checker" vs "specaware checker"）
            # 将每个实体拆分为单词集合进行匹配
            def entity_to_word_set(entity: str) -> set:
                """将实体转换为单词集合"""
                normalized = normalize_entity(entity)
                # 提取所有单词（处理连字符、驼峰等）
                words = re.findall(r'[a-z0-9]+', normalized.lower())
                return set(words) if words else {normalized}
            
            gt_word_sets = [entity_to_word_set(e) for e in gt_entities]
            gen_word_sets = [entity_to_word_set(e) for e in gen_entities]
            
            # 检查每个标准答案实体是否在生成的答案中有匹配的实体
            # 匹配标准：实体的所有单词都在某个生成实体中出现
            matched_gt_entities = 0
            for gt_word_set in gt_word_sets:
                if not gt_word_set:
                    continue
                for gen_word_set in gen_word_sets:
                    # 如果标准实体的所有单词都在生成实体中，认为匹配
                    if gt_word_set.issubset(gen_word_set) or gen_word_set.issubset(gt_word_set):
                        matched_gt_entities += 1
                        break
            
            # 如果所有标准答案实体都找到了匹配，认为正确
            if matched_gt_entities == len(gt_entities) and len(gt_entities) > 0:
                return True
            
            # 5. 回退到关键词匹配（单词级别，忽略连接词）
            gt_words = normalized_ground_truth.split()
            gen_words = normalized_generated.split()
            
            gt_keywords = {w for w in gt_words if w not in CONJUNCTIONS}
            gen_keywords = {w for w in gen_words if w not in CONJUNCTIONS}
            
            # 如果标准答案的所有关键词都在生成的答案中，认为正确
            if gt_keywords and gt_keywords.issubset(gen_keywords):
                return True
            
            return False
        
        # 默认情况：精确匹配
        return normalized_generated == normalized_ground_truth


class SigLIPScore(BaseMetric):
    """SigLIP 视觉语义相似度"""
    
    def __init__(self):
        super().__init__("siglip_score")
        self.model = None
        self.processor = None
        self.current_gpu_id = 0  # 当前使用的GPU ID
    
    def _load_model(self, gpu_id: int = 0):
        """加载 SigLIP 模型"""
        try:
            from transformers import SiglipModel, SiglipProcessor
            import torch
            
            # 检查是否有 GPU，如果没有则报错（不使用CPU）
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available. This metric requires GPU.")
            
            # 检查GPU数量
            num_gpus = torch.cuda.device_count()
            if gpu_id >= num_gpus:
                raise RuntimeError(f"GPU {gpu_id} is not available. Only {num_gpus} GPU(s) available.")
            
            # 模型配置：可以替换为其他可用的 SigLIP 模型
            # 可用模型选项：
            # - "google/siglip-base-patch16-224" (较小，速度快)
            # - "google/siglip-base-patch16-256" (中等)
            # - "google/siglip-large-patch16-256" (较大，精度高)
            # - "google/siglip-so400m-patch14-384" (当前默认)
            model_checkpoint = "google/siglip2-so400m-patch16-512"
            self.processor = SiglipProcessor.from_pretrained(model_checkpoint)
            self.model = SiglipModel.from_pretrained(model_checkpoint)
            
            # 使用指定的GPU
            device = f"cuda:{gpu_id}"
            self.current_gpu_id = gpu_id
            self.model = self.model.to(device)
            
            # 使用半精度以减少显存占用
            try:
                self.model = self.model.half()
                logger.info(f"SigLIP model converted to half precision (fp16) to save memory")
            except Exception as e:
                logger.warning(f"Failed to convert model to half precision: {e}")
            
            self.model.eval()
            
            # 清理显存缓存
            torch.cuda.empty_cache()
            
            logger.info(f"SigLIP model loaded on {device} (GPU {gpu_id}/{num_gpus})")
        except ImportError:
            logger.warning("transformers library not available, SigLIP will not work")
            self.model = None
            self.processor = None
        except Exception as e:
            logger.error(f"Failed to load SigLIP model: {e}")
            self.model = None
            self.processor = None
    
    def _switch_to_next_gpu(self):
        """切换到下一张GPU"""
        import torch
        
        if not torch.cuda.is_available():
            return False
        
        num_gpus = torch.cuda.device_count()
        if num_gpus <= 1:
            logger.warning("Only one GPU available, cannot switch")
            return False
        
        # 计算下一张GPU的ID
        next_gpu_id = (self.current_gpu_id + 1) % num_gpus
        
        logger.info(f"Switching from GPU {self.current_gpu_id} to GPU {next_gpu_id}")
        
        try:
            # 清理当前GPU的显存
            torch.cuda.empty_cache()
            
            # 将模型移动到新的GPU
            device = f"cuda:{next_gpu_id}"
            self.model = self.model.to(device)
            self.current_gpu_id = next_gpu_id
            
            # 清理新GPU的显存
            torch.cuda.empty_cache()
            
            logger.info(f"Successfully switched to GPU {next_gpu_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to GPU {next_gpu_id}: {e}")
            return False
    
    def evaluate(
        self,
        original_image_path: Path,
        rendered_image_path: Path,
        execution_success: bool = True,
        **kwargs
    ) -> MetricResult:
        """
        计算 SigLIP 相似度得分
        
        Args:
            original_image_path: 原图路径
            rendered_image_path: 渲染图路径
            execution_success: XML 是否执行成功
        """
        # 如果执行失败，直接返回 0.0
        if not execution_success:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "Execution failed"},
                success=True
            )
        
        # 检查渲染图是否存在
        if not rendered_image_path.exists():
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "Rendered image not found"},
                success=True
            )
        
        if not self.model or not self.processor:
            self._load_model()

        if not self.model or not self.processor:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                details={"error": "SigLIP model not available"},
                success=False,
                error_message="SigLIP model not available"
            )
        
        # 导入必要的库
        from PIL import Image
        import torch
        import torch.nn.functional as F
        
        # 最多尝试所有可用的GPU
        max_retries = torch.cuda.device_count() if torch.cuda.is_available() else 1
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                
                device = next(self.model.parameters()).device
                
                # 清理显存缓存
                torch.cuda.empty_cache()
                
                # 加载图像
                image1 = Image.open(original_image_path).convert("RGB")
                image2 = Image.open(rendered_image_path).convert("RGB")
                
                # 预处理
                inputs1 = self.processor(images=[image1], return_tensors="pt")
                inputs2 = self.processor(images=[image2], return_tensors="pt")
                
                # 移动到设备并转换为半精度（如果模型是半精度）
                if next(self.model.parameters()).dtype == torch.float16:
                    inputs1 = {k: v.to(device).half() if v.dtype == torch.float32 else v.to(device) 
                              for k, v in inputs1.items()}
                    inputs2 = {k: v.to(device).half() if v.dtype == torch.float32 else v.to(device) 
                              for k, v in inputs2.items()}
                else:
                    inputs1 = {k: v.to(device) for k, v in inputs1.items()}
                    inputs2 = {k: v.to(device) for k, v in inputs2.items()}
                
                # 提取特征 - 分别处理以节省显存
                with torch.no_grad():
                    # 处理第一张图像
                    emb1 = self.model.get_image_features(**inputs1)
                    emb1 = F.normalize(emb1, p=2, dim=-1)
                    
                    # 清理中间变量
                    del inputs1
                    torch.cuda.empty_cache()
                    
                    # 处理第二张图像
                    emb2 = self.model.get_image_features(**inputs2)
                    emb2 = F.normalize(emb2, p=2, dim=-1)
                    
                    # 清理中间变量
                    del inputs2
                    torch.cuda.empty_cache()
                
                # 计算余弦相似度
                similarity = F.cosine_similarity(emb1, emb2, dim=-1).item()
                
                # 清理特征向量
                del emb1, emb2
                torch.cuda.empty_cache()
                
                return MetricResult(
                    metric_name=self.name,
                    score=float(similarity),
                    details={
                        "similarity": float(similarity),
                        "model_checkpoint": "google/siglip2-so400m-patch16-512",
                        "gpu_id": self.current_gpu_id
                    },
                    success=True
                )
            except torch.cuda.OutOfMemoryError as e:
                retry_count += 1
                logger.warning(f"CUDA out of memory on GPU {self.current_gpu_id}: {e}")
                
                # 清理当前GPU的显存
                torch.cuda.empty_cache()
                
                # 尝试切换到下一张GPU
                if retry_count < max_retries:
                    if self._switch_to_next_gpu():
                        logger.info(f"Retrying on GPU {self.current_gpu_id} (attempt {retry_count + 1}/{max_retries})")
                        continue
                    else:
                        logger.error("Failed to switch to next GPU")
                        break
                else:
                    logger.error(f"All {max_retries} GPU(s) ran out of memory")
                    break
            except Exception as e:
                logger.error(f"Error computing SigLIP score: {e}", exc_info=True)
                # 清理显存
                torch.cuda.empty_cache()
                return MetricResult(
                    metric_name=self.name,
                    score=None,
                    details={"error": str(e)},
                    success=False,
                    error_message=str(e)
                )
        
        # 如果所有GPU都失败了
        return MetricResult(
            metric_name=self.name,
            score=None,
            details={"error": "CUDA out of memory on all GPUs"},
            success=False,
            error_message="CUDA out of memory on all GPUs"
        )
