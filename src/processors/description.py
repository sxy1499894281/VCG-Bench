"""
Description generation module
"""

import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from ..core.models import ImageInfo, StructuredDescription
from ..llm.client import LLMClient

logger = logging.getLogger(__name__)


class DescriptionGenerator:
    """
    Generate structured descriptions from images using LLM
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0
    ):
        """
        Args:
            llm_client: LLM client instance (creates new if None)
            provider: LLM provider name
            model: Model name (uses provider default if None)
            temperature: Sampling temperature
        """
        self.llm_client = llm_client or LLMClient()
        self.provider = provider
        self.model = model
        self.temperature = temperature

    def generate_description(
        self,
        image_info: ImageInfo,
        use_llm: bool = True
    ) -> Tuple[StructuredDescription, Dict[str, Any]]:
        """
        Generate structured description for an image

        Args:
            image_info: Image to describe
            use_llm: If False, create a placeholder description

        Returns:
            Tuple of (StructuredDescription, token_usage_stats)
        """
        logger.info(f"Generating description for: {image_info.filename}")

        if not use_llm:
            return self._create_placeholder_description(image_info), {}

        try:
            # Build context
            context_text = self._build_context(image_info)

            # Call LLM to get structured JSON description
            description_dict, usage_stats = self.llm_client.describe_image(
                image_input=image_info.path,
                context_text=context_text,
                provider=self.provider,
                model=self.model,
                temperature=self.temperature
            )

            # Parse JSON dict into StructuredDescription
            # Map the JSON fields to StructuredDescription fields
            description = self._parse_json_to_structured_description(
                description_dict,
                image_info,
                usage_stats
            )

            logger.info(
                f"Description generated: {description.diagram_type}, "
                f"{len(description.components)} components, "
                f"{len(description.relationships)} relationships, "
                f"tokens: {usage_stats.get('total_tokens', 0)}"
            )

            return description, usage_stats

        except Exception as e:
            logger.error(f"Description generation failed for {image_info.filename}: {e}")
            raise

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

    def _parse_json_to_structured_description(
        self,
        description_dict: Dict[str, Any],
        image_info: ImageInfo,
        usage_stats: Dict[str, Any]
    ) -> StructuredDescription:
        """Parse JSON description dict into StructuredDescription object"""
        
        # Extract components from JSON
        components = []
        if isinstance(description_dict.get('components'), list):
            for comp in description_dict['components']:
                if isinstance(comp, dict):
                    components.append({
                        "id": comp.get('name', ''),
                        "type": comp.get('type', 'unknown'),
                        "label": comp.get('name', ''),
                        "description": comp.get('description', '')
                    })
        
        # Extract relationships from arrows.details
        relationships = []
        arrows_details = description_dict.get('arrows', {}).get('details', [])
        if isinstance(arrows_details, list):
            for arrow in arrows_details:
                if isinstance(arrow, dict):
                    relationships.append({
                        "source": arrow.get('from', ''),
                        "target": arrow.get('to', ''),
                        "type": arrow.get('style', 'unknown'),
                        "label": arrow.get('label', '')
                    })
        
        # Extract spatial layout
        spatial_layout = description_dict.get('spatial_layout')
        if spatial_layout and isinstance(spatial_layout, dict):
            # Convert to the format expected by StructuredDescription
            spatial_layout = {
                "type": spatial_layout.get('primary_layout', 'unknown'),
                "direction": spatial_layout.get('primary_layout', ''),
                "layers": spatial_layout.get('relative_positions', [])
            }
        
        # Extract color scheme
        color_scheme = description_dict.get('color_palette')
        if color_scheme and isinstance(color_scheme, dict):
            colors = color_scheme.get('colors', [])
            if colors:
                color_scheme = {}
                for color_info in colors:
                    if isinstance(color_info, dict):
                        name = color_info.get('name', '')
                        hex_val = color_info.get('hex', '')
                        if name and hex_val:
                            color_scheme[name.lower()] = hex_val
        
        # Build metadata with all original JSON data
        metadata = {
            "from_llm": True,
            "filename": image_info.filename,
            "caption": image_info.caption,
            "token_usage": usage_stats,
            # Store the full JSON for reference
            "raw_json": description_dict
        }
        
        # Create StructuredDescription
        description = StructuredDescription(
            diagram_type=description_dict.get('image_type', 'unknown'),
            title=image_info.figure_label or description_dict.get('overview', image_info.filename),
            summary=description_dict.get('overview', ''),
            components=components,
            relationships=relationships,
            spatial_layout=spatial_layout,
            color_scheme=color_scheme,
            annotations=description_dict.get('structural_patterns', []),
            metadata=metadata
        )
        
        return description

    def _create_placeholder_description(self, image_info: ImageInfo) -> StructuredDescription:
        """Create a placeholder description (for testing without LLM)"""
        return StructuredDescription(
            diagram_type="unknown",
            title=image_info.figure_label or image_info.filename,
            summary=image_info.caption or "No description available (LLM disabled)",
            components=[],
            relationships=[],
            metadata={
                "placeholder": True,
                "filename": image_info.filename
            }
        )
