"""
Drawio XML renderer - converts XML to PNG images
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import tempfile
import shutil

from ..core.models import DiagramXML
from ..core.constants import DEFAULT_RENDER_FORMAT, DEFAULT_RENDER_DPI, DEFAULT_RENDER_SCALE

logger = logging.getLogger(__name__)


class DrawioRenderer:
    """
    Render Drawio XML diagrams to images

    Supports multiple rendering backends:
    1. Drawio CLI (draw.io desktop app)
    2. Headless Chrome/Puppeteer
    3. drawio-batch (if available)
    """

    def __init__(
        self,
        backend: str = 'drawio-cli',
        drawio_path: Optional[Path] = None,
        skip_render: bool = False
    ):
        """
        Args:
            backend: Rendering backend ('drawio-cli', 'puppeteer', 'headless')
            drawio_path: Path to drawio executable (auto-detect if None)
            skip_render: Skip actual rendering (for HPC environments without draw.io)
        """
        self.backend = backend

        if drawio_path is None:
            env_drawio_path = os.getenv("DRAWIO_PATH")
            if env_drawio_path:
                env_path = Path(env_drawio_path).expanduser()
                if env_path.exists():
                    drawio_path = env_path
                else:
                    logger.warning("DRAWIO_PATH is set but does not exist: %s", env_path)

        self.drawio_path = drawio_path or self._find_drawio()
        self.skip_render = skip_render

        if self.backend == 'drawio-cli' and not self.drawio_path and not skip_render:
            logger.warning("Drawio CLI not found. Rendering will be disabled.")

    def render(
        self,
        diagram: DiagramXML,
        output_path: Path,
        format: str = DEFAULT_RENDER_FORMAT,
        scale: float = DEFAULT_RENDER_SCALE,
        transparent: bool = False
    ) -> bool:
        """
        Render diagram to image file

        Args:
            diagram: DiagramXML object
            output_path: Output file path
            format: Output format ('png', 'svg', 'pdf')
            scale: Scaling factor
            transparent: Transparent background

        Returns:
            True if successful
        """
        # Skip-render mode: check if image already exists
        if self.skip_render:
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Skip-render mode: Using existing {output_path}")
                return True
            else:
                logger.warning(f"Skip-render mode: Image not found at {output_path}")
                return False

        logger.info(f"Rendering diagram to {output_path}")

        # Even if diagram.is_valid is False, we still attempt rendering.
        # This allows downstream inspection of raw XML and lets Draw.io
        # decide whether it can render the file.
        if not diagram.is_valid:
            logger.warning("Diagram marked invalid by validator; attempting render anyway")

        # Create temporary XML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            f.write(diagram.xml_content)
            temp_xml = Path(f.name)

        try:
            if self.backend == 'drawio-cli':
                success = self._render_with_drawio_cli(
                    temp_xml, output_path, format, scale, transparent
                )
            elif self.backend == 'puppeteer':
                success = self._render_with_puppeteer(
                    temp_xml, output_path, format, scale, transparent
                )
            else:
                logger.error(f"Unsupported backend: {self.backend}")
                success = False

            if success:
                logger.info(f"Successfully rendered to {output_path}")
            else:
                logger.error(f"Rendering failed")

            return success

        finally:
            # Clean up temp file
            temp_xml.unlink(missing_ok=True)

    def _find_drawio(self) -> Optional[Path]:
        """
        Try to find Drawio executable on the system

        Common locations:
        - macOS: /Applications/draw.io.app/Contents/MacOS/draw.io
        - Linux: /usr/bin/drawio, /usr/local/bin/drawio, /snap/bin/drawio
        - Linux AppImage: ~/Applications/drawio-*.AppImage, ~/Downloads/drawio-*.AppImage
        - Windows: C:\\Program Files\\draw.io\\draw.io.exe
        """
        import os
        home_dir = Path.home()
        
        candidates = [
            # macOS
            Path("/Applications/draw.io.app/Contents/MacOS/draw.io"),
            Path("/Applications/drawio.app/Contents/MacOS/drawio"),
            # Linux - system paths
            Path("/usr/bin/drawio"),
            Path("/usr/local/bin/drawio"),
            Path("/snap/bin/drawio"),
            # Linux - AppImage common locations
            home_dir / "Applications" / "drawio-x86_64.AppImage",
            home_dir / "Downloads" / "drawio-x86_64.AppImage",
            home_dir / ".local" / "bin" / "drawio",
            # Windows
            Path("C:/Program Files/draw.io/draw.io.exe"),
            Path("C:/Program Files (x86)/draw.io/draw.io.exe"),
        ]
        
        # Try to find AppImage files in common locations
        for search_dir in [home_dir / "Applications", home_dir / "Downloads", Path("/opt")]:
            if search_dir.exists():
                try:
                    for appimage in search_dir.glob("drawio*.AppImage"):
                        if appimage.is_file() and os.access(appimage, os.X_OK):
                            candidates.append(appimage)
                except (PermissionError, OSError):
                    pass

        for path in candidates:
            if path.exists():
                # Check if file is executable (for AppImage)
                if path.is_file() and not os.access(path, os.X_OK):
                    try:
                        # Try to make it executable (for AppImage)
                        os.chmod(path, 0o755)
                    except (PermissionError, OSError):
                        logger.warning(f"Found drawio at {path} but cannot make it executable")
                        continue
                logger.info(f"Found drawio at: {path}")
                return path

        # Try which/where command (Linux/macOS)
        try:
            result = subprocess.run(
                ['which', 'drawio'],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            path = Path(result.stdout.strip())
            if path.exists():
                logger.info(f"Found drawio via which: {path}")
                return path
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.warning("Drawio executable not found")
        return None

    def _render_with_drawio_cli(
        self,
        xml_path: Path,
        output_path: Path,
        format: str,
        scale: float,
        transparent: bool
    ) -> bool:
        """
        Render using Drawio CLI

        Command format (supports both short and long options):
        - Short: drawio -x -f <format> -s <scale> -t -o <output> <input>
        - Long:  drawio --export --format <format> --scale <scale> --transparent --output <output> <input>
        
        For Linux headless environments, adds --no-sandbox flag if needed.
        """
        if not self.drawio_path or not self.drawio_path.exists():
            logger.error("Drawio executable not available")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build command with short options (more compatible across versions)
        cmd = [
            str(self.drawio_path),
            '-x',  # Export
            '-f', format,
            '-s', str(scale),
            '-o', str(output_path),
            str(xml_path)
        ]

        if transparent:
            # Insert -t before -o (at index -3, which is the position of '-o')
            # Command structure: [drawio, '-x', '-f', format, '-s', scale, '-o', output, input]
            # We want: [drawio, '-x', '-f', format, '-s', scale, '-t', '-o', output, input]
            cmd.insert(-3, '-t')  # Insert before '-o' option
        
        # Add --no-sandbox for Linux headless environments (AppImage may need this)
        # Check if running on Linux and if drawio is an AppImage
        import platform
        is_linux = platform.system() == 'Linux'
        is_appimage = str(self.drawio_path).endswith('.AppImage') or 'AppImage' in str(self.drawio_path)
        
        if is_linux and is_appimage:
            # Insert --no-sandbox before the input file
            cmd.insert(-1, '--no-sandbox')
            logger.debug("Added --no-sandbox flag for Linux AppImage")

        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # Increased timeout for complex diagrams
                check=False
            )

            if result.returncode == 0 and output_path.exists():
                logger.debug(f"Drawio CLI succeeded")
                return True
            else:
                # Enhanced error logging
                error_msg = result.stderr.strip() if result.stderr else "No error message"
                stdout_msg = result.stdout.strip() if result.stdout else "No output"
                logger.error(f"Drawio CLI failed (returncode={result.returncode})")
                logger.error(f"Error output: {error_msg}")
                if stdout_msg:
                    logger.debug(f"Standard output: {stdout_msg}")
                
                # Try alternative command format if short options fail
                if result.returncode != 0 and is_linux:
                    logger.info("Attempting with long option format...")
                    return self._render_with_long_options(xml_path, output_path, format, scale, transparent)
                
                return False

        except subprocess.TimeoutExpired:
            logger.error("Drawio rendering timed out after 60 seconds")
            return False
        except Exception as e:
            logger.error(f"Drawio rendering error: {e}", exc_info=True)
            return False
    
    def _render_with_long_options(
        self,
        xml_path: Path,
        output_path: Path,
        format: str,
        scale: float,
        transparent: bool
    ) -> bool:
        """
        Alternative render method using long option format
        drawio --export --format <format> --scale <scale> --output <output> <input>
        """
        cmd = [
            str(self.drawio_path),
            '--export',
            '--format', format,
            '--scale', str(scale),
            '--output', str(output_path),
        ]
        
        if transparent:
            cmd.append('--transparent')
        
        # Add --no-sandbox for Linux AppImage
        import platform
        is_linux = platform.system() == 'Linux'
        is_appimage = str(self.drawio_path).endswith('.AppImage') or 'AppImage' in str(self.drawio_path)
        if is_linux and is_appimage:
            cmd.append('--no-sandbox')
        
        cmd.append(str(xml_path))
        
        logger.debug(f"Trying long options: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )
            
            if result.returncode == 0 and output_path.exists():
                logger.info("Drawio CLI succeeded with long options")
                return True
            else:
                logger.error(f"Long options also failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Long options render error: {e}")
            return False

    def _render_with_puppeteer(
        self,
        xml_path: Path,
        output_path: Path,
        format: str,
        scale: float,
        transparent: bool
    ) -> bool:
        """
        Render using Puppeteer/headless browser

        This is a placeholder. Real implementation would:
        1. Start a local HTTP server
        2. Load draw.io viewer in headless Chrome
        3. Take screenshot
        """
        logger.warning("Puppeteer backend not implemented")
        return False

    def can_render(self) -> bool:
        """Check if rendering is available"""
        if self.backend == 'drawio-cli':
            return self.drawio_path is not None and self.drawio_path.exists()
        return False
