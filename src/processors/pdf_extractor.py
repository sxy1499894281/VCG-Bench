"""
PDF image extraction using MinerU wrapper
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import shutil

from ..core.models import ImageInfo, PaperMetadata

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    PDF image extraction using MinerU (magic-pdf)
    Wraps MinerU CLI and parses output structure
    """

    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: Directory to store parsed papers
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_pdf(
        self,
        pdf_path: Path,
        paper_id: Optional[str] = None
    ) -> PaperMetadata:
        """
        Extract images from PDF using MinerU

        Args:
            pdf_path: Path to PDF file
            paper_id: Optional paper identifier (uses filename if None)

        Returns:
            PaperMetadata with parsing results
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if paper_id is None:
            paper_id = pdf_path.stem

        logger.info(f"Extracting PDF: {pdf_path} -> {paper_id}")

        # Create output directory for this paper
        paper_output = self.output_dir / paper_id / "auto"
        paper_output.mkdir(parents=True, exist_ok=True)

        # Run MinerU extraction
        try:
            self._run_mineru(pdf_path, paper_output)
        except Exception as e:
            logger.error(f"MinerU extraction failed: {e}")
            raise

        # Parse MinerU output structure
        metadata = self._parse_mineru_output(paper_output, paper_id)
        logger.info(f"Extracted {metadata.total_images} images from {pdf_path.name}")

        return metadata

    def _run_mineru(self, pdf_path: Path, output_dir: Path):
        """
        Run MinerU CLI to extract PDF

        Note: This is a placeholder. Real implementation should use:
        - magic-pdf CLI tool
        - or magic-pdf Python API if available
        """
        import subprocess

        # Example command (adjust based on MinerU installation)
        # magic-pdf -p <pdf_path> -o <output_dir>
        cmd = [
            "magic-pdf",
            "-p", str(pdf_path),
            "-o", str(output_dir)
        ]

        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"MinerU stdout: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"MinerU failed: {e.stderr}")
            raise RuntimeError(f"MinerU extraction failed: {e.stderr}")
        except FileNotFoundError:
            logger.warning("MinerU (magic-pdf) not found. Creating placeholder structure.")
            # For testing: create placeholder structure
            self._create_placeholder_structure(output_dir)

    def _create_placeholder_structure(self, output_dir: Path):
        """Create placeholder structure for testing without MinerU"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create placeholder content_list.json
        placeholder_content = {
            "pdf_info": {"total_pages": 10},
            "content": [],
            "images": []
        }

        content_list_path = output_dir / "content_list.json"
        with open(content_list_path, 'w', encoding='utf-8') as f:
            json.dump(placeholder_content, f, indent=2)

        # Create images directory
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        logger.warning(f"Created placeholder structure at {output_dir}")

    def _parse_mineru_output(
        self,
        output_dir: Path,
        paper_id: str
    ) -> PaperMetadata:
        """
        Parse MinerU output structure

        Expected structure:
        output_dir/
          ├── *_content_list.json  (required)
          ├── *_model.json         (optional)
          ├── *.md                 (optional)
          └── images/              (required)
              ├── image_001.png
              ├── image_002.png
              └── ...
        """
        # Find content_list.json
        content_list_files = list(output_dir.glob("*_content_list.json"))
        if not content_list_files:
            content_list_files = list(output_dir.glob("content_list.json"))

        if not content_list_files:
            logger.warning(f"No content_list.json found in {output_dir}")
            content_data = {}
        else:
            with open(content_list_files[0], 'r', encoding='utf-8') as f:
                content_data = json.load(f)

        # Count total pages
        total_pages = content_data.get('pdf_info', {}).get('total_pages', 0)

        # Find images directory
        images_dir = output_dir / "images"
        if images_dir.exists():
            image_files = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
            total_images = len(image_files)
        else:
            total_images = 0
            logger.warning(f"No images directory found in {output_dir}")

        metadata = PaperMetadata(
            paper_id=paper_id,
            parsed_path=output_dir,
            total_pages=total_pages,
            total_images=total_images
        )

        return metadata

    def load_images(self, paper_metadata: PaperMetadata) -> List[ImageInfo]:
        """
        Load image information from parsed paper

        Args:
            paper_metadata: Paper metadata from extract_pdf()

        Returns:
            List of ImageInfo objects
        """
        if not paper_metadata.parsed_path:
            raise ValueError("Paper metadata has no parsed_path")

        images_dir = paper_metadata.parsed_path / "images"
        if not images_dir.exists():
            logger.warning(f"Images directory not found: {images_dir}")
            return []

        # Load content_list.json for image metadata
        content_list_files = list(paper_metadata.parsed_path.glob("*_content_list.json"))
        if not content_list_files:
            content_list_files = list(paper_metadata.parsed_path.glob("content_list.json"))

        image_metadata_map = {}
        if content_list_files:
            with open(content_list_files[0], 'r', encoding='utf-8') as f:
                content_data = json.load(f)
                # Extract image metadata from content_data
                for item in content_data.get('content', []):
                    if item.get('type') == 'image':
                        img_path = item.get('img_path', '')
                        image_metadata_map[Path(img_path).name] = {
                            'caption': item.get('img_caption', ''),
                            'page_number': item.get('page_idx', 0)
                        }

        # Collect all image files
        image_infos = []
        for img_path in sorted(images_dir.glob("*.png")) + sorted(images_dir.glob("*.jpg")):
            try:
                from PIL import Image
                with Image.open(img_path) as img:
                    width, height = img.size
                    img_format = img.format
            except Exception as e:
                logger.warning(f"Failed to read image {img_path}: {e}")
                width, height, img_format = None, None, None

            # Get metadata from content_list
            meta = image_metadata_map.get(img_path.name, {})

            image_info = ImageInfo(
                path=img_path,
                filename=img_path.name,
                width=width,
                height=height,
                format=img_format,
                size_bytes=img_path.stat().st_size,
                caption=meta.get('caption'),
                page_number=meta.get('page_number')
            )
            image_infos.append(image_info)

        logger.info(f"Loaded {len(image_infos)} images from {paper_metadata.paper_id}")
        return image_infos
