"""
Unified LLM client for vision tasks (classification, description, diagram generation)
"""

import base64
import json
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path

from .providers import get_provider, BaseProvider
from ..core.constants import DEFAULT_LLM_TEMPERATURE, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client supporting multiple providers (SiliconFlow, Zhipu, Custom)
    Singleton pattern for efficient reuse
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.providers: Dict[str, BaseProvider] = {}
        self._initialized = True
        logger.info("LLMClient initialized (singleton)")

    def _get_provider(self, provider_name: str) -> BaseProvider:
        """Get or create a provider instance"""
        if provider_name not in self.providers:
            self.providers[provider_name] = get_provider(provider_name)
            logger.info(f"Initialized provider: {provider_name}")
        return self.providers[provider_name]

    @staticmethod
    def _encode_image(image_input: Union[bytes, Path, str]) -> str:
        """Encode image to base64 data URL"""
        if isinstance(image_input, (Path, str)):
            with open(image_input, 'rb') as f:
                image_bytes = f.read()
        else:
            image_bytes = image_input

        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        # Assume PNG for simplicity; could detect MIME type
        return f"data:image/png;base64,{base64_image}"

    def _call_vision_api(
        self,
        prompt: str,
        image_input: Union[bytes, Path, str, List[Union[bytes, Path, str]]],
        provider: str,
        model: Optional[str] = None,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
        response_format: Optional[Dict[str, str]] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Internal method to call vision API with unified interface

        Args:
            prompt: Text prompt
            image_input: Image as bytes, Path, file path string, or list of images for multi-image input
            provider: Provider name ('siliconflow', 'zhipu', 'custom')
            model: Model name (uses provider default if None)
            temperature: Sampling temperature
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Tuple of (response_text, usage_stats)
            usage_stats: {
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
                "model": str,
                "provider": str
            }
        """
        provider_obj = self._get_provider(provider)
        client = provider_obj.get_client()

        if model is None:
            model = provider_obj.get_default_model()

        # Handle single image or multiple images
        if isinstance(image_input, list):
            # Multiple images
            image_urls = [self._encode_image(img) for img in image_input]
            content = [{"type": "text", "text": prompt}]
            for image_url in image_urls:
                content.append({"type": "image_url", "image_url": {"url": image_url}})
        else:
            # Single image (backward compatibility)
            image_url = self._encode_image(image_input)
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]

        # Build messages
        messages = [
            {
                "role": "user",
                "content": content
            }
        ]

        # Call API with retry logic
        logger.debug(f"Calling {provider}/{model} with temperature={temperature}")
        logger.info(f"API call - provider: {provider}, model: {model}, temperature: {temperature}")

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # Retry logic: try up to 3 times (initial attempt + 2 retries)
        max_retries = 2
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying API call (attempt {attempt + 1}/{max_retries + 1}) after {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                
                response = client.chat.completions.create(**kwargs)
                
                # Handle different response types (some APIs return string instead of object)
                if isinstance(response, str):
                    # Response is already a string - check if it's HTML (error page)
                    response_lower = response.strip().lower()
                    if response_lower.startswith('<!doctype') or response_lower.startswith('<html'):
                        # Check if this is a specific HTTP error (e.g., 524 Cloudflare timeout)
                        if '524' in response_lower or 'error 524' in response_lower or 'cloudflare' in response_lower:
                            # 524 错误表示服务器端超时，不应该重试，避免重复计费
                            error_msg = f"API returned HTML error page (HTTP 524/Cloudflare timeout). Server-side timeout detected - aborting to avoid duplicate billing. URL: {provider_obj._current_base_url if hasattr(provider_obj, '_current_base_url') else 'unknown'}, First 500 chars: {response[:500]}"
                            logger.error(error_msg)
                            logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request. Retrying would cause duplicate requests and billing.")
                            raise ValueError(error_msg)
                        else:
                            # API returned HTML instead of JSON - likely an incorrect endpoint or server error
                            error_msg = f"API returned HTML page instead of JSON response. This usually indicates an incorrect endpoint or server error. URL: {provider_obj._current_base_url if hasattr(provider_obj, '_current_base_url') else 'unknown'}, First 500 chars: {response[:500]}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    
                    # Try to parse as JSON
                    logger.warning(f"API returned string instead of object, type: {type(response)}, first 200 chars: {response[:200]}")
                    try:
                        # Try to parse as JSON first
                        response_dict = json.loads(response)
                        # If it's a JSON object with choices, extract content
                        if isinstance(response_dict, dict) and 'choices' in response_dict:
                            response_text = response_dict['choices'][0].get('message', {}).get('content', response)
                            # Extract usage if available
                            usage_info = response_dict.get('usage', {})
                        else:
                            # JSON but not the expected structure
                            error_msg = f"API returned JSON but with unexpected structure. Expected 'choices' key. Keys: {list(response_dict.keys()) if isinstance(response_dict, dict) else 'not a dict'}"
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                    except json.JSONDecodeError:
                        # Not valid JSON - this is an error
                        error_msg = f"API returned non-JSON string response that couldn't be parsed. First 500 chars: {response[:500]}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    except (KeyError, IndexError) as e:
                        # JSON parsing succeeded but structure is wrong
                        error_msg = f"API returned JSON but with incorrect structure: {e}. Response keys: {list(response_dict.keys()) if isinstance(response_dict, dict) else 'not a dict'}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                else:
                    # Standard OpenAI-compatible response object
                    response_text = response.choices[0].message.content
                    usage_info = response.usage if hasattr(response, 'usage') and response.usage else None

                # Extract token usage
                usage_stats = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "model": model,
                    "provider": provider
                }

                if usage_info:
                    if isinstance(usage_info, dict):
                        usage_stats["prompt_tokens"] = usage_info.get('prompt_tokens', 0)
                        usage_stats["completion_tokens"] = usage_info.get('completion_tokens', 0)
                        usage_stats["total_tokens"] = usage_info.get('total_tokens', 0)
                    else:
                        # usage_info is an object with attributes
                        usage_stats["prompt_tokens"] = getattr(usage_info, 'prompt_tokens', 0)
                        usage_stats["completion_tokens"] = getattr(usage_info, 'completion_tokens', 0)
                        usage_stats["total_tokens"] = getattr(usage_info, 'total_tokens', 0)

                logger.debug(f"Received response: {len(response_text)} chars, tokens: {usage_stats['total_tokens']}")
                if attempt > 0:
                    logger.info(f"API call succeeded on retry attempt {attempt + 1}")
                logger.info(f"Token usage - Prompt: {usage_stats['prompt_tokens']}, Completion: {usage_stats['completion_tokens']}, Total: {usage_stats['total_tokens']}")

                return response_text, usage_stats
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # 检测 524 错误（Cloudflare 超时）- 立即失败，不重试，避免重复计费
                # 524 错误表示服务器端超时，如果重试可能导致服务器同时处理多个请求并重复计费
                if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                    logger.error(f"HTTP 524 Cloudflare timeout error detected - aborting immediately to avoid duplicate billing. Error: {e}")
                    logger.error(f"Failed request details - provider: {provider}, model: {model}")
                    logger.error("NOTE: 524 errors indicate server-side timeout. Retrying may cause duplicate requests and billing.")
                    raise  # 立即抛出异常，不重试
                
                if attempt < max_retries:
                    logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    logger.warning(f"Failed request details - provider: {provider}, model: {model}")
                else:
                    logger.error(f"API call failed after {max_retries + 1} attempts: {e}")
                    logger.error(f"Failed request details - provider: {provider}, model: {model}")
        
        # All retries exhausted
        raise last_exception

    def classify_diagram(
        self,
        image_input: Union[bytes, Path, str],
        context_text: Optional[str] = None,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Classify if an image is a candidate diagram (flowchart, architecture, etc.)

        Args:
            image_input: Image to classify
            context_text: Optional context (caption, surrounding text)
            provider: LLM provider to use
            model: Model name (uses provider default if None)
            temperature: Sampling temperature (0.0 for deterministic)

        Returns:
            Tuple of (classification_result, usage_stats)
            classification_result: {
                "is_candidate": bool,
                "score": float (0.0-1.0),
                "reason": str,
                "diagram_type": str or None
            }
            usage_stats: Token usage information
        """
        from configs.prompts import get_classification_prompt

        prompt = get_classification_prompt(context_text)

        try:
            response_text, usage_stats = self._call_vision_api(
                prompt=prompt,
                image_input=image_input,
                provider=provider,
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"}
            )

            # Parse JSON response
            result = json.loads(response_text)
            logger.info(f"Classification: is_candidate={result.get('is_candidate')}, score={result.get('score')}")
            return result, usage_stats

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response as JSON: {e}")
            # Fallback: keyword matching
            return {
                "is_candidate": False,
                "score": 0.0,
                "reason": "LLM response parsing failed",
                "diagram_type": None
            }, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model": model or "unknown", "provider": provider}
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            raise

    def describe_image(
        self,
        image_input: Union[bytes, Path, str],
        context_text: Optional[str] = None,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Generate a structured JSON description of a diagram.

        This method expects and parses JSON output from the model, returning
        a complete structured description dictionary that matches the schema
        defined in the prompt (components, arrows, spatial_layout, etc.).

        Args:
            image_input: Image to describe
            context_text: Optional context (caption, surrounding text)
            provider: LLM provider to use
            model: Model name
            temperature: Sampling temperature

        Returns:
            Tuple of (description_dict, usage_stats)
            description_dict: Complete structured JSON description
        """
        from configs.prompts import get_description_prompt

        prompt = get_description_prompt(context_text)

        try:
            response_text, usage_stats = self._call_vision_api(
                prompt=prompt,
                image_input=image_input,
                provider=provider,
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"}
            )

            # Parse JSON response
            try:
                description_dict = json.loads(response_text)
                logger.info(f"Description JSON parsed successfully ({len(response_text)} chars)")
                return description_dict, usage_stats
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse description response as JSON: {e}")
                logger.warning(f"Raw response (first 500 chars): {response_text[:500]}")
                # Fallback: return as text in a dict
                return {"text": response_text, "parse_error": str(e)}, usage_stats

        except Exception as e:
            logger.error(f"Description generation failed: {e}")
            raise

    def generate_diagram_xml(
        self,
        image_input: Union[bytes, Path, str],
        description: Optional[Dict[str, Any]] = None,
        context_text: Optional[str] = None,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Generate Drawio XML from image and optional description

        Args:
            image_input: Image to convert
            description: Optional pre-generated structured description
            context_text: Optional context
            provider: LLM provider to use
            model: Model name
            temperature: Sampling temperature

        Returns:
            Tuple of (xml_result, usage_stats)
            xml_result: {
                "xml": str,
                "metadata": {
                    "node_count": int,
                    "edge_count": int,
                    "diagram_type": str
                }
            }
            usage_stats: Token usage information
        """
        from configs.prompts import get_diagram_prompt

        prompt = get_diagram_prompt(description, context_text)

        try:
            response_text, usage_stats = self._call_vision_api(
                prompt=prompt,
                image_input=image_input,
                provider=provider,
                model=model,
                temperature=temperature
            )

            # Extract XML from response (may be wrapped in JSON or markdown code blocks)
            xml_content = self._extract_xml(response_text)

            # Parse metadata
            metadata = self._parse_xml_metadata(xml_content)

            logger.info(f"XML generated: {metadata.get('node_count')} nodes, {metadata.get('edge_count')} edges")

            return {
                "xml": xml_content,
                "metadata": metadata
            }, usage_stats

        except Exception as e:
            logger.error(f"Diagram XML generation failed: {e}")
            raise

    @staticmethod
    def _extract_xml(response_text: str) -> str:
        """Extract XML content from LLM response"""
        # Try to find XML in code blocks
        if "```xml" in response_text:
            start = response_text.find("```xml") + 6
            end = response_text.find("```", start)
            return response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            return response_text[start:end].strip()
        # Try to find raw XML
        elif "<mxGraphModel" in response_text:
            start = response_text.find("<mxGraphModel")
            end = response_text.rfind("</mxGraphModel>") + len("</mxGraphModel>")
            if end > start:
                return response_text[start:end]

        # Fallback: return as-is
        return response_text

    @staticmethod
    def _parse_xml_metadata(xml_content: str) -> Dict[str, Any]:
        """Parse metadata from XML content"""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_content)

            # Count nodes and edges
            node_count = len(root.findall(".//mxCell[@vertex='1']"))
            edge_count = len(root.findall(".//mxCell[@edge='1']"))

            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "is_valid": True
            }
        except ET.ParseError as e:
            logger.warning(f"XML parsing failed: {e}")
            return {
                "node_count": 0,
                "edge_count": 0,
                "is_valid": False,
                "error": str(e)
            }

    def edit_xml_incremental(
        self,
        original_xml: str,
        instruction: str,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0,
        stream: bool = False
    ) -> List[Dict[str, str]]:
        """
        根据指令编辑XML（增量格式，节省token）
        
        注意：只使用XML和指令，不使用图片。模型需要根据指令中的自然语言描述
        在XML中找到对应的元素进行修改。
        
        Args:
            original_xml: 原始XML内容
            instruction: 修改指令（自然语言，基于视觉描述，但模型需要映射到XML）
            provider: LLM provider
            model: Model name
            temperature: Sampling temperature
            
        Returns:
            增量修改列表，每个元素包含：
            [
                {
                    "original_fragment": "原始XML片段",
                    "modified_fragment": "修改后的XML片段"
                },
                ...
            ]
            注意：可能返回多个修改，因为修改的地方可能不止一处
        """
        from configs.prompts import get_xml_editing_incremental_prompt
        
        prompt = get_xml_editing_incremental_prompt(original_xml, instruction)
        
        try:
            # 使用文本API（不传入图片，只使用XML和指令）
            # 使用最大 token 限制，不限制模型的能力，让模型按最大能力输出
            response_text, usage_stats = self._call_text_api(
                prompt=prompt,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=None,  # None 表示不限制，让模型按最大能力输出（某些API不支持max_tokens参数）
                response_format={"type": "json_object"},
                stream=stream
            )
            
            # 保存token使用信息（供后续使用）
            self._last_token_usage = usage_stats
            
            # 清理响应文本（移除 Markdown 代码块标记，如果存在）
            cleaned_response = response_text.strip()
            # 处理 Markdown 代码块（如 ```json ... ```）
            if cleaned_response.startswith("```json"):
                # 移除开头的 ```json
                cleaned_response = cleaned_response[7:].strip()
                # 移除结尾的 ```
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3].strip()
            elif cleaned_response.startswith("```"):
                # 移除开头的 ```
                cleaned_response = cleaned_response[3:].strip()
                # 移除结尾的 ```
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3].strip()
            
            # 解析JSON响应
            try:
                result = json.loads(cleaned_response)
                # 提取增量修改列表
                if isinstance(result, dict) and "changes" in result:
                    incremental_changes = result["changes"]
                elif isinstance(result, list):
                    incremental_changes = result
                else:
                    logger.warning(f"Unexpected response format: {type(result)}")
                    incremental_changes = []
                
                # 验证格式
                validated_changes = []
                for change in incremental_changes:
                    if isinstance(change, dict) and "original_fragment" in change and "modified_fragment" in change:
                        validated_changes.append({
                            "original_fragment": change["original_fragment"],
                            "modified_fragment": change.get("modified_fragment", "")
                        })
                    else:
                        logger.warning(f"Invalid change format: {change}")
                
                return validated_changes
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.warning(f"Raw response: {response_text[:500]}")
                
                # 检查是否是截断导致的错误（可重试）
                # 如果响应看起来不完整（如以未完成的字符串结尾），可能是截断
                is_truncated = False
                
                # 检查响应末尾是否看起来不完整（主要判断方式）
                # 因为现在使用 DEFAULT_MAX_TOKENS（无限制），不能通过 token 数量判断截断
                response_end = cleaned_response[-100:].strip() if len(cleaned_response) > 100 else cleaned_response.strip()
                if (not response_end.endswith('}') and not response_end.endswith(']') and 
                    ('"' in response_end or '{' in response_end or '[' in response_end)):
                    # 响应末尾有未闭合的引号、括号等，可能是截断
                    is_truncated = True
                
                # 如果响应以未完成的 JSON 结构结尾，也可能是截断
                if not is_truncated and len(cleaned_response) > 0:
                    # 检查是否以未完成的字符串结尾（如 "text": "unfinished...）
                    if cleaned_response.rstrip().endswith('"') and cleaned_response.count('"') % 2 != 0:
                        is_truncated = True
                
                # 抛出异常，包含错误信息，让上层处理
                error_msg = f"JSON parsing failed: {e}"
                if is_truncated:
                    error_msg += " (likely truncated response)"
                raise ValueError(error_msg) from e
                
        except Exception as e:
            logger.error(f"XML editing failed: {e}")
            raise

    def _call_text_api(
        self,
        prompt: str,
        provider: str,
        model: Optional[str] = None,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
        max_tokens: Optional[int] = 4096,
        response_format: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> tuple[str, Dict[str, Any]]:
        """
        Internal method to call text API with unified interface
        
        Args:
            prompt: Text prompt
            provider: Provider name
            model: Model name (uses provider default if None)
            temperature: Sampling temperature
            max_tokens: Maximum tokens (None means no limit, let model use maximum capability)
            response_format: Optional response format (e.g., {"type": "json_object"})
            stream: Whether to use streaming API calls (default: False)
            
        Returns:
            Tuple of (response_text, usage_stats)
        """
        provider_obj = self._get_provider(provider)
        client = provider_obj.get_client()
        
        if model is None:
            model = provider_obj.get_default_model()
        
        # Build messages
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        # Call API
        logger.debug(f"Calling {provider}/{model} with temperature={temperature}")
        logger.info(f"API call - provider: {provider}, model: {model}, temperature: {temperature}")
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        
        # Only add max_tokens if it's not None (some APIs don't support this parameter)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        
        if response_format:
            kwargs["response_format"] = response_format
        
        # Retry logic: try up to 3 times (initial attempt + 2 retries)
        max_retries = 2
        last_exception = None
        max_tokens_removed = False  # Track if we've removed max_tokens due to error
        response_format_removed = False  # Track if we've removed response_format due to error
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff: wait 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying API call (attempt {attempt + 1}/{max_retries + 1}) after {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                
                # If previous attempt failed with max_tokens error, remove it from kwargs
                if attempt > 0 and not max_tokens_removed:
                    error_str = str(last_exception).lower()
                    if 'max_tokens' in error_str and ('invalid' in error_str or 'not supported' in error_str):
                        logger.warning(f"API doesn't support max_tokens parameter, removing it for retry")
                        kwargs.pop('max_tokens', None)
                        max_tokens_removed = True
                
                # If previous attempt failed with response_format error, remove it from kwargs
                if attempt > 0 and not response_format_removed:
                    error_str = str(last_exception).lower()
                    if ('response_format' in error_str or 'response format' in error_str) and ('invalid' in error_str or 'not supported' in error_str or 'unsupported' in error_str):
                        logger.warning(f"API doesn't support response_format parameter, removing it for retry")
                        kwargs.pop('response_format', None)
                        response_format_removed = True
                
                response = client.chat.completions.create(**kwargs)
                
                # Handle streaming response
                if stream:
                    response_text = ""
                    usage_info = None
                    for chunk in response:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta and delta.content:
                                response_text += delta.content
                        # Extract usage from last chunk if available
                        if hasattr(chunk, 'usage') and chunk.usage:
                            usage_info = chunk.usage
                    # If no usage in chunks, try to get from response object
                    if usage_info is None and hasattr(response, 'usage'):
                        usage_info = response.usage
                # Handle different response types (some APIs return string instead of object)
                elif isinstance(response, str):
                    # Response is already a string - check if it's HTML (error page)
                    response_lower = response.strip().lower()
                    if response_lower.startswith('<!doctype') or response_lower.startswith('<html'):
                        # Check if this is a specific HTTP error (e.g., 524 Cloudflare timeout)
                        if '524' in response_lower or 'error 524' in response_lower or 'cloudflare' in response_lower:
                            # 524 错误表示服务器端超时，不应该重试，避免重复计费
                            error_msg = f"API returned HTML error page (HTTP 524/Cloudflare timeout). Server-side timeout detected - aborting to avoid duplicate billing. URL: {provider_obj._current_base_url if hasattr(provider_obj, '_current_base_url') else 'unknown'}, First 500 chars: {response[:500]}"
                            logger.error(error_msg)
                            logger.error("NOTE: 524 errors indicate server-side timeout. The server may still be processing the request. Retrying would cause duplicate requests and billing.")
                            raise ValueError(error_msg)
                        else:
                            # API returned HTML instead of JSON - likely an incorrect endpoint or server error
                            error_msg = f"API returned HTML page instead of JSON response. This usually indicates an incorrect endpoint or server error. URL: {provider_obj._current_base_url if hasattr(provider_obj, '_current_base_url') else 'unknown'}, First 500 chars: {response[:500]}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    
                    # Try to parse as JSON
                    logger.warning(f"API returned string instead of object, type: {type(response)}, first 200 chars: {response[:200]}")
                    try:
                        # Try to parse as JSON first
                        response_dict = json.loads(response)
                        # If it's a JSON object with choices, extract content
                        if isinstance(response_dict, dict) and 'choices' in response_dict:
                            response_text = response_dict['choices'][0].get('message', {}).get('content', response)
                            # Extract usage if available
                            usage_info = response_dict.get('usage', {})
                        else:
                            # JSON but not the expected structure
                            error_msg = f"API returned JSON but with unexpected structure. Expected 'choices' key. Keys: {list(response_dict.keys()) if isinstance(response_dict, dict) else 'not a dict'}"
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                    except json.JSONDecodeError:
                        # Not valid JSON - this is an error
                        error_msg = f"API returned non-JSON string response that couldn't be parsed. First 500 chars: {response[:500]}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    except (KeyError, IndexError) as e:
                        # JSON parsing succeeded but structure is wrong
                        error_msg = f"API returned JSON but with incorrect structure: {e}. Response keys: {list(response_dict.keys()) if isinstance(response_dict, dict) else 'not a dict'}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                else:
                    # Standard OpenAI-compatible response object (non-streaming)
                    response_text = response.choices[0].message.content
                    usage_info = response.usage if hasattr(response, 'usage') and response.usage else None
                
                # Extract token usage
                usage_stats = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "model": model,
                    "provider": provider
                }
                
                if usage_info:
                    if isinstance(usage_info, dict):
                        usage_stats["prompt_tokens"] = usage_info.get('prompt_tokens', 0)
                        usage_stats["completion_tokens"] = usage_info.get('completion_tokens', 0)
                        usage_stats["total_tokens"] = usage_info.get('total_tokens', 0)
                    else:
                        # usage_info is an object with attributes
                        usage_stats["prompt_tokens"] = getattr(usage_info, 'prompt_tokens', 0)
                        usage_stats["completion_tokens"] = getattr(usage_info, 'completion_tokens', 0)
                        usage_stats["total_tokens"] = getattr(usage_info, 'total_tokens', 0)
                
                logger.debug(f"Received response: {len(response_text)} chars, tokens: {usage_stats['total_tokens']}")
                if attempt > 0:
                    logger.info(f"API call succeeded on retry attempt {attempt + 1}")
                logger.info(f"Token usage - Prompt: {usage_stats['prompt_tokens']}, Completion: {usage_stats['completion_tokens']}, Total: {usage_stats['total_tokens']}")
                
                return response_text, usage_stats
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # 检测 524 错误（Cloudflare 超时）- 立即失败，不重试，避免重复计费
                # 524 错误表示服务器端超时，如果重试可能导致服务器同时处理多个请求并重复计费
                if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                    logger.error(f"HTTP 524 Cloudflare timeout error detected - aborting immediately to avoid duplicate billing. Error: {e}")
                    logger.error(f"Failed request details - provider: {provider}, model: {model}")
                    logger.error("NOTE: 524 errors indicate server-side timeout. Retrying may cause duplicate requests and billing.")
                    raise  # 立即抛出异常，不重试
                
                if attempt < max_retries:
                    logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    logger.warning(f"Failed request details - provider: {provider}, model: {model}")
                else:
                    logger.error(f"API call failed after {max_retries + 1} attempts: {e}")
                    logger.error(f"Failed request details - provider: {provider}, model: {model}")
        
        # All retries exhausted
        raise last_exception
