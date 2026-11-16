"""Image processing: framing, light & color, segmentation and background compositing."""

from selficamera.processor.background import BackgroundCompositor
from selficamera.processor.framing import AutoFramer, CropRect, compute_crop
from selficamera.processor.lighting import ImageAdjuster
from selficamera.processor.pipeline import FrameProcessor
from selficamera.processor.segmentation import SegmentationEngine

__all__ = [
    "AutoFramer",
    "BackgroundCompositor",
    "CropRect",
    "FrameProcessor",
    "ImageAdjuster",
    "SegmentationEngine",
    "compute_crop",
]
