"""
Constants and configuration defaults
"""

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}

# LLM defaults
DEFAULT_LLM_TEMPERATURE = 0.0
# Use int32 max value (2147483647) to effectively mean "no limit"
# This works with all APIs that require max_tokens (within int32 range)
# For providers that don't support max_tokens (like Gemini proxies), use None instead
# Note: For task2, we use None to let models use maximum capability without token limits
DEFAULT_MAX_TOKENS = 2147483647  # int32 max value, effectively unlimited(99999999999999)

# Screening defaults
DEFAULT_SCREENING_THRESHOLD = 0.6
SCREENING_KEYWORDS = [
    "flowchart", "flow chart", "workflow", "pipeline",
    "architecture", "system diagram", "block diagram",
    "network diagram", "topology", "process flow",
    "data flow", "sequence diagram", "state machine"
]

# Description generation
# Use int32 max value to effectively mean "no limit"
DEFAULT_DESCRIPTION_MAX_TOKENS = 2147483647  # int32 max value
MIN_COMPONENT_COUNT = 2

# Diagram generation
DEFAULT_DIAGRAM_MAX_TOKENS = 2147483647  # int32 max value
MAX_REPAIR_ATTEMPTS = 3

# XML validation
DRAWIO_REQUIRED_TAGS = ['mxGraphModel', 'root', 'mxCell']
DRAWIO_NAMESPACE = 'mxGraphModel'

# Rendering defaults
DEFAULT_RENDER_FORMAT = 'png'
DEFAULT_RENDER_DPI = 300
DEFAULT_RENDER_SCALE = 1.0

# File naming
IMAGE_OUTPUT_PATTERN = "image_{index:03d}"
DESCRIPTION_FILENAME = "llm_description.json"
DIAGRAM_FILENAME = "diagram.xml"
RENDERED_FILENAME = "diagram_drawio.png"
METADATA_FILENAME = "meta.json"

# Context extraction (for workflow 1)
DEFAULT_CONTEXT_WINDOW_BEFORE = 200
DEFAULT_CONTEXT_WINDOW_AFTER = 500
MAX_CONTEXT_LENGTH = 2000

# Batch processing
DEFAULT_BATCH_SIZE = 10
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1.0

# Logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
