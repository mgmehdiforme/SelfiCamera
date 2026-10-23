"""V4L2 Camera device enumeration and capability discovery."""

from __future__ import annotations

import fcntl
import glob
import logging
import os
import struct
from dataclasses import dataclass, field
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Linux V4L2 constants
# VIDIOC_QUERYCAP: _IOR('V', 0, struct v4l2_capability)
# sizeof(struct v4l2_capability) = 16 + 32 + 32 + 4 + 4 + 4 + 12 = 104 bytes
VIDIOC_QUERYCAP = 0x80685600
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_DEVICE_CAPS = 0x80000000

STANDARD_RESOLUTIONS: List[Tuple[int, int]] = [
    (640, 480),
    (1280, 720),
    (1920, 1080),
]


@dataclass
class VideoDeviceInfo:
    """Information regarding an enumerated video capture device."""
    device_path: str
    card_name: str
    driver: str = ""
    bus_info: str = ""
    is_capture: bool = True
    supported_resolutions: List[Tuple[int, int]] = field(default_factory=lambda: list(STANDARD_RESOLUTIONS))

    @property
    def display_name(self) -> str:
        """Formatted display name for UI dropdowns and tray menus."""
        return f"{self.card_name} ({self.device_path})"


class V4L2DeviceScanner:
    """Scans and queries /dev/video* devices for video capture capabilities."""

    @staticmethod
    def query_device_capability(device_path: str) -> VideoDeviceInfo | None:
        """Query a single video node using V4L2 ioctl VIDIOC_QUERYCAP."""
        if not os.path.exists(device_path):
            return None

        try:
            fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        except (OSError, PermissionError) as e:
            logger.debug("Cannot open %s: %s", device_path, e)
            return None

        try:
            # struct v4l2_capability layout:
            # 16s: driver
            # 32s: card
            # 32s: bus_info
            # I: version
            # I: capabilities
            # I: device_caps
            # 3I: reserved[3]
            v4l2_cap_fmt = "16s32s32sIII3I"
            buf = bytearray(struct.calcsize(v4l2_cap_fmt))
            fcntl.ioctl(fd, VIDIOC_QUERYCAP, buf)
            unpacked = struct.unpack(v4l2_cap_fmt, buf)

            driver = unpacked[0].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
            card = unpacked[1].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
            bus_info = unpacked[2].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
            capabilities = unpacked[4]
            device_caps = unpacked[5]

            # If V4L2_CAP_DEVICE_CAPS is set, verify device_caps, else capabilities
            active_caps = device_caps if (capabilities & V4L2_CAP_DEVICE_CAPS) else capabilities
            is_capture = bool(active_caps & V4L2_CAP_VIDEO_CAPTURE)

            if not is_capture:
                logger.debug("Device %s is not a video capture node", device_path)
                return None

            return VideoDeviceInfo(
                device_path=device_path,
                card_name=card or f"Webcam ({os.path.basename(device_path)})",
                driver=driver,
                bus_info=bus_info,
                is_capture=True,
            )
        except Exception as e:
            logger.debug("ioctl VIDIOC_QUERYCAP failed on %s: %s", device_path, e)
            return None
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    @classmethod
    def list_devices(cls) -> List[VideoDeviceInfo]:
        """Enumerate all capture-capable /dev/video* devices sorted by index."""
        device_paths = sorted(
            glob.glob("/dev/video[0-9]*"),
            key=lambda p: int(p.replace("/dev/video", "")) if p.replace("/dev/video", "").isdigit() else 999
        )

        devices: List[VideoDeviceInfo] = []
        for path in device_paths:
            info = cls.query_device_capability(path)
            if info is not None:
                devices.append(info)

        return devices
