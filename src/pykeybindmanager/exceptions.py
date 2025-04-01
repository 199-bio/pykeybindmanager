"""
Custom exceptions for the PyKeybindManager module.
"""

class KeybindManagerError(Exception):
    """Base exception for KeybindManager errors."""
    pass

class ListenerError(KeybindManagerError):
    """Exception raised for errors during listener setup or execution."""
    pass

class PermissionError(ListenerError):
    """Exception raised specifically for OS permission issues (e.g., Input Monitoring)."""
    pass

class InvalidKeybindError(KeybindManagerError):
    """Exception raised when an invalid keybind string or object is provided."""
    pass

class PynputImportError(KeybindManagerError, ImportError):
    """Exception raised if the pynput library cannot be imported."""
    pass
