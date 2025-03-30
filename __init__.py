"""
PyKeybindManager - A simple keybind listener module using pynput.
"""
import logging

# Configure logging for the module package
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

# Import main class and exceptions for easier access
from .manager import KeybindManager, KeybindManagerError
from .keys import parse_keybind_string # Helper to parse string representations
from .exceptions import ListenerError, PermissionError, InvalidKeybindError, PynputImportError
from .sound_player import play_sound_file # Import sound player utility

# Define what gets imported with 'from pykeybindmanager import *'
__all__ = [
    'KeybindManager',
    'KeybindManagerError',
    'ListenerError',
    'PermissionError',
    'InvalidKeybindError',
    'PynputImportError',
    'parse_keybind_string',
    'play_sound_file' # Export sound player
]

# Optional: Define a version for the module
__version__ = "0.2.0" # Updated version
