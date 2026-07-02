"""
File operation utilities
"""

import hashlib
import logging
import shutil
from pathlib import Path
from typing import List, Optional
import re

from ..core.constants import SUPPORTED_IMAGE_FORMATS

logger = logging.getLogger(__name__)


def find_images(
    directory: Path,
    recursive: bool = True,
    formats: Optional[set] = None
) -> List[Path]:
    """
    Find all image files in a directory

    Args:
        directory: Directory to search
        recursive: Search recursively
        formats: Set of file extensions (default: SUPPORTED_IMAGE_FORMATS)

    Returns:
        List of image file paths, sorted
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if formats is None:
        formats = SUPPORTED_IMAGE_FORMATS

    logger.info(f"Searching for images in {directory} (recursive={recursive})")

    images = []
    pattern = "**/*" if recursive else "*"

    for ext in formats:
        # Handle extensions with or without dot
        ext_clean = ext if ext.startswith('.') else f'.{ext}'
        images.extend(directory.glob(f"{pattern}{ext_clean}"))
        # Also try uppercase
        images.extend(directory.glob(f"{pattern}{ext_clean.upper()}"))

    # Remove duplicates and sort
    images = sorted(set(images))

    logger.info(f"Found {len(images)} images")
    return images


def safe_filename(filename: str, max_length: int = 200) -> str:
    """
    Convert a string to a safe filename

    Args:
        filename: Original filename
        max_length: Maximum length

    Returns:
        Safe filename string
    """
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Remove control characters
    safe = re.sub(r'[\x00-\x1f\x7f]', '', safe)

    # Collapse multiple underscores/spaces
    safe = re.sub(r'[_\s]+', '_', safe)

    # Trim
    safe = safe.strip('._')

    # Enforce max length (preserve extension)
    if len(safe) > max_length:
        name, ext = Path(safe).stem, Path(safe).suffix
        name = name[:max_length - len(ext) - 1]
        safe = f"{name}{ext}"

    return safe


def ensure_dir(path: Path, parents: bool = True) -> Path:
    """
    Ensure directory exists, create if needed

    Args:
        path: Directory path
        parents: Create parent directories

    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=parents, exist_ok=True)
    return path


def get_file_hash(file_path: Path, algorithm: str = 'md5') -> str:
    """
    Compute hash of file contents

    Args:
        file_path: File to hash
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')

    Returns:
        Hex digest string
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hash_obj = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def copy_with_metadata(src: Path, dst: Path, overwrite: bool = False) -> Path:
    """
    Copy file preserving metadata

    Args:
        src: Source file
        dst: Destination path
        overwrite: Whether to overwrite existing file

    Returns:
        Destination path
    """
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    if dst.exists() and not overwrite:
        logger.debug(f"Destination exists, skipping: {dst}")
        return dst

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.debug(f"Copied {src} -> {dst}")

    return dst


def relative_path(path: Path, base: Path) -> Path:
    """
    Get relative path from base

    Args:
        path: Target path
        base: Base path

    Returns:
        Relative path
    """
    try:
        return Path(path).relative_to(base)
    except ValueError:
        # Not relative, return as-is
        return Path(path)


def format_size(size_bytes: int) -> str:
    """
    Format file size in human-readable form

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def list_directory_tree(directory: Path, max_depth: int = 3, indent: str = "") -> str:
    """
    Generate a tree representation of directory structure

    Args:
        directory: Root directory
        max_depth: Maximum depth to traverse
        indent: Current indentation (internal)

    Returns:
        Tree string
    """
    directory = Path(directory)
    if not directory.exists():
        return f"{indent}[Not found: {directory}]"

    lines = [f"{indent}{directory.name}/"]

    if max_depth <= 0:
        lines.append(f"{indent}  ...")
        return "\n".join(lines)

    try:
        items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        for item in items:
            if item.is_dir():
                subtree = list_directory_tree(item, max_depth - 1, indent + "  ")
                lines.append(subtree)
            else:
                size = format_size(item.stat().st_size)
                lines.append(f"{indent}  {item.name} ({size})")
    except PermissionError:
        lines.append(f"{indent}  [Permission denied]")

    return "\n".join(lines)
