"""Lightweight blob rendering engine for Pi Zero 2W.

Stripped-down metaball renderer optimised for 512MB RAM / 1GHz ARM.
Renders at 64x64, upscales to display size via pygame.transform.scale.
"""

from blob.renderer import BlobRendererLite
from blob.states import BlobStateLite, STATE_CONFIGS_LITE
from blob.gestures import GestureQueueLite

__all__ = ["BlobRendererLite", "BlobStateLite", "STATE_CONFIGS_LITE", "GestureQueueLite"]
