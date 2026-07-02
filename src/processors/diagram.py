"""
Diagram XML generation module
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from ..core.models import ImageInfo, StructuredDescription, DiagramXML
from ..core.constants import MAX_REPAIR_ATTEMPTS, DRAWIO_REQUIRED_TAGS
from ..llm.client import LLMClient

logger = logging.getLogger(__name__)


class DiagramGenerator:
    """
    Generate Drawio XML diagrams from images and descriptions
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        provider: str = 'custom',
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_repair_attempts: int = MAX_REPAIR_ATTEMPTS
    ):
        """
        Args:
            llm_client: LLM client instance (creates new if None)
            provider: LLM provider name
            model: Model name (uses provider default if None)
            temperature: Sampling temperature
            max_repair_attempts: Maximum number of repair attempts for invalid XML
        """
        self.llm_client = llm_client or LLMClient()
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_repair_attempts = max_repair_attempts

    def generate_diagram(
        self,
        image_info: ImageInfo,
        description: Optional[StructuredDescription] = None,
        use_llm: bool = True
    ) -> Tuple[DiagramXML, Dict[str, Any]]:
        """
        Generate Drawio XML diagram

        Args:
            image_info: Image to convert
            description: Optional pre-generated description
            use_llm: If False, create a placeholder diagram

        Returns:
            Tuple of (DiagramXML, token_usage_stats)
        """
        logger.info(f"Generating diagram XML for: {image_info.filename}")

        if not use_llm:
            return self._create_placeholder_diagram(image_info), {}

        start_time = time.time()
        repair_attempts = 0

        try:
            # Build context
            context_text = self._build_context(image_info)

            # Call LLM to generate XML
            # Use raw JSON from metadata if available, otherwise use to_dict()
            description_dict = None
            if description:
                # Prefer raw JSON from metadata (complete structured description)
                if isinstance(description.metadata, dict) and 'raw_json' in description.metadata:
                    description_dict = description.metadata['raw_json']
                else:
                    # Fallback to to_dict() if raw_json not available
                    description_dict = description.to_dict()
            
            result, usage_stats = self.llm_client.generate_diagram_xml(
                image_input=image_info.path,
                description=description_dict,
                context_text=context_text,
                provider=self.provider,
                model=self.model,
                temperature=self.temperature
            )

            xml_content = result['xml']
            metadata = result.get('metadata', {})

            # Validate XML
            validation_result = self._validate_xml(xml_content)

            # Log validation errors but skip repair for now (too costly)
            # TODO: Add repair step with dedicated prompt + error info + original XML
            if not validation_result['is_valid']:
                logger.warning(
                    f"XML validation failed: {validation_result['errors']}. "
                    f"Skipping repair (disabled to save costs)."
                )

            generation_time = time.time() - start_time

            diagram = DiagramXML(
                xml_content=xml_content,
                diagram_type=metadata.get('diagram_type', 'unknown'),
                node_count=metadata.get('node_count', 0),
                edge_count=metadata.get('edge_count', 0),
                is_valid=validation_result['is_valid'],
                validation_errors=validation_result['errors'],
                model_used=self.model or 'default',
                generation_time=generation_time,
                repair_attempts=repair_attempts,
                metadata={**metadata, 'token_usage': usage_stats}  # Add token stats
            )

            logger.info(
                f"Diagram generated: {diagram.node_count} nodes, {diagram.edge_count} edges, "
                f"valid={diagram.is_valid}, repairs={repair_attempts}, "
                f"tokens: {usage_stats.get('total_tokens', 0)}"
            )

            return diagram, usage_stats

        except Exception as e:
            logger.error(f"Diagram generation failed for {image_info.filename}: {e}")
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

    def _validate_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Validate Drawio XML structure

        Returns:
            {
                "is_valid": bool,
                "errors": List[str]
            }
        """
        errors = []

        try:
            # Parse XML
            root = ET.fromstring(xml_content)

            # Check for required tags. ElementTree .findall(".//tag") searches
            # descendants only, so include the root element itself.
            for tag in DRAWIO_REQUIRED_TAGS:
                if root.tag != tag and not root.findall(f".//{tag}"):
                    errors.append(f"Missing required tag: {tag}")

            # Check for at least one node or edge
            nodes = root.findall(".//mxCell[@vertex='1']")
            edges = root.findall(".//mxCell[@edge='1']")

            if not nodes and not edges:
                errors.append("No nodes or edges found in diagram")

        except ET.ParseError as e:
            errors.append(f"XML parsing error: {e}")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }

    def _attempt_repair(
        self,
        image_info: ImageInfo,
        description: Optional[StructuredDescription],
        broken_xml: str,
        errors: list
    ) -> str:
        """
        Attempt to repair broken XML

        For simplicity, this just regenerates with a note about the errors.
        A more sophisticated approach would use the LLM to fix specific issues.
        """
        logger.info(f"Attempting XML repair for {image_info.filename}")

        # For now, just try regenerating
        # In production, you might want to send the errors back to LLM for repair
        try:
            context_text = self._build_context(image_info)
            result = self.llm_client.generate_diagram_xml(
                image_input=image_info.path,
                description=description.to_dict() if description else None,
                context_text=context_text,
                provider=self.provider,
                model=self.model,
                temperature=self.temperature + 0.1  # Slightly higher temperature
            )
            return result['xml']
        except Exception as e:
            logger.error(f"Repair attempt failed: {e}")
            return broken_xml

    def _create_placeholder_diagram(self, image_info: ImageInfo) -> DiagramXML:
        """Create a placeholder diagram (for testing without LLM)"""

        # Minimal valid Drawio XML
        placeholder_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="2024-01-01T00:00:00.000Z" agent="placeholder" version="1.0.0">
  <diagram name="Placeholder">
    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="Placeholder Node" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">
          <mxGeometry x="340" y="280" width="120" height="60" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""

        return DiagramXML(
            xml_content=placeholder_xml,
            diagram_type="placeholder",
            node_count=1,
            edge_count=0,
            is_valid=True,
            validation_errors=[],
            metadata={
                "placeholder": True,
                "filename": image_info.filename
            }
        )
