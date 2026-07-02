"""
Image screening/classification module
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..core.models import ImageInfo
from ..core.constants import DEFAULT_SCREENING_THRESHOLD, SCREENING_KEYWORDS
from ..llm.client import LLMClient

logger = logging.getLogger(__name__)


class ImageScreener:
    """
    Screen images to identify diagram candidates (flowcharts, architectures, etc.)
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0,
        threshold: float = DEFAULT_SCREENING_THRESHOLD
    ):
        """
        Args:
            llm_client: LLM client instance (creates new if None)
            provider: LLM provider name
            model: Model name (uses provider default if None)
            temperature: Sampling temperature
            threshold: Classification threshold (0.0-1.0)
        """
        self.llm_client = llm_client or LLMClient()
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.threshold = threshold

    def screen_image(
        self,
        image_info: ImageInfo,
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Screen a single image

        Args:
            image_info: Image information
            use_llm: If True, use LLM; if False, use keyword fallback

        Returns:
            {
                "is_candidate": bool,
                "score": float,
                "reason": str,
                "diagram_type": str or None
            }
        """
        logger.info(f"Screening image: {image_info.filename}")

        # Try LLM classification
        if use_llm:
            try:
                result = self.llm_client.classify_diagram(
                    image_input=image_info.path,
                    context_text=self._build_context(image_info),
                    provider=self.provider,
                    model=self.model,
                    temperature=self.temperature
                )

                # Apply threshold
                is_candidate = result.get('score', 0.0) >= self.threshold
                result['is_candidate'] = is_candidate

                logger.info(
                    f"LLM screening: {image_info.filename} -> "
                    f"candidate={is_candidate}, score={result.get('score'):.2f}"
                )
                return result

            except Exception as e:
                logger.error(f"LLM screening failed for {image_info.filename}: {e}")
                logger.info("Falling back to keyword screening")

        # Fallback: keyword-based screening
        return self._keyword_screening(image_info)

    def _build_context(self, image_info: ImageInfo) -> Optional[str]:
        """Build context text from image metadata"""
        context_parts = []

        if image_info.caption:
            context_parts.append(f"Caption: {image_info.caption}")

        if image_info.figure_label:
            context_parts.append(f"Label: {image_info.figure_label}")

        if image_info.context_text:
            context_parts.append(f"Context: {image_info.context_text}")

        return "\n".join(context_parts) if context_parts else None

    def _keyword_screening(self, image_info: ImageInfo) -> Dict[str, Any]:
        """Fallback keyword-based screening"""
        context = self._build_context(image_info) or ""
        context_lower = context.lower()

        # Check for diagram keywords
        matched_keywords = [kw for kw in SCREENING_KEYWORDS if kw.lower() in context_lower]

        is_candidate = len(matched_keywords) > 0
        score = min(len(matched_keywords) * 0.3, 1.0)

        logger.info(
            f"Keyword screening: {image_info.filename} -> "
            f"candidate={is_candidate}, matched={matched_keywords}"
        )

        return {
            "is_candidate": is_candidate,
            "score": score,
            "reason": f"Keyword match: {matched_keywords}" if matched_keywords else "No keywords matched",
            "diagram_type": "keyword_match" if matched_keywords else None,
            "matched_keywords": matched_keywords
        }

    def screen_batch(
        self,
        image_infos: List[ImageInfo],
        use_llm: bool = True,
        top_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Screen a batch of images

        Args:
            image_infos: List of images to screen
            use_llm: Whether to use LLM
            top_n: Keep only top N candidates (by score)

        Returns:
            List of screening results with original image_info
        """
        logger.info(f"Screening batch of {len(image_infos)} images")

        results = []
        for image_info in image_infos:
            try:
                screening_result = self.screen_image(image_info, use_llm=use_llm)
                results.append({
                    "image_info": image_info,
                    "screening": screening_result
                })
            except Exception as e:
                logger.error(f"Failed to screen {image_info.filename}: {e}")
                results.append({
                    "image_info": image_info,
                    "screening": {
                        "is_candidate": False,
                        "score": 0.0,
                        "reason": f"Screening error: {e}",
                        "diagram_type": None
                    }
                })

        # Sort by score
        results.sort(key=lambda x: x['screening'].get('score', 0.0), reverse=True)

        # Filter candidates
        candidates = [r for r in results if r['screening'].get('is_candidate', False)]
        logger.info(f"Found {len(candidates)} candidates out of {len(results)} images")

        # Apply top_n filter
        if top_n is not None and len(candidates) > top_n:
            logger.info(f"Keeping top {top_n} candidates")
            kept = results[:top_n]
            # Mark remaining as not candidates
            for r in results[top_n:]:
                r['screening']['is_candidate'] = False
                r['screening']['reason'] = f"Outside top {top_n}"
            results = kept + results[top_n:]

        return results
