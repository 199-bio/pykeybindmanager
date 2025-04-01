"""
Helper functions for parsing keybind strings into modifier sets and pynput key objects.
"""
import sys
import logging
from .exceptions import InvalidKeybindError, PynputImportError

logger = logging.getLogger(__name__)

# Attempt to import pynput - parsing relies on it
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    keyboard = None
    # Raise PynputImportError later if needed

# Special mapping for macOS FN key (Virtual Key Code 179)
MACOS_FN_VK = 179

# Define modifier keys (lowercase) and their pynput equivalents
# Use platform-specific command key
_CMD_KEY = keyboard.Key.cmd if sys.platform == 'darwin' else keyboard.Key.ctrl
MODIFIER_MAP = {
    'ctrl': keyboard.Key.ctrl,
    'alt': keyboard.Key.alt,
    'shift': keyboard.Key.shift,
    'cmd': _CMD_KEY,
    'meta': _CMD_KEY, # Alias for cmd/ctrl
    # 'fn' is treated as a regular key due to its special handling needs
}

def _parse_single_key(key_part):
    """Parses a single part of the key string (modifier or main key)."""
    key_part_lower = key_part.lower()

    # Handle macOS 'fn' key specifically
    if key_part_lower == 'fn' and sys.platform == 'darwin':
        # Treat 'fn' as a main key, not a modifier in the traditional sense
        return keyboard.KeyCode.from_vk(MACOS_FN_VK)
    elif key_part_lower == 'fn':
        logger.warning("Parsing 'fn' key requested on non-macOS platform. This might not work as expected.")
        # Attempt to find a generic 'fn' if pynput defines one, otherwise fail later
        if hasattr(keyboard.Key, 'fn'):
            return keyboard.Key.fn
        else:
            # Let the main parser handle the error if no other match found
            return None # Indicate failure to parse 'fn' here

    # Check if it's a known modifier
    if key_part_lower in MODIFIER_MAP:
        return MODIFIER_MAP[key_part_lower]

    # Check if it's a special key defined in keyboard.Key (non-modifier)
    if hasattr(keyboard.Key, key_part_lower):
        return getattr(keyboard.Key, key_part_lower)

    # Check if it's a single character key
    if len(key_part) == 1:
        try:
            # Use from_char for printable characters
            return keyboard.KeyCode.from_char(key_part)
        except ValueError:
            # This might happen for non-standard single characters
             raise InvalidKeybindError(f"Could not parse single character '{key_part}'")

    # If none of the above match
    return None


def parse_keybind_string(keybind_string):
    """
    Parses a keybind string (e.g., "f1", "ctrl+alt+t", "cmd+shift+p", "fn")
    into a tuple containing a frozenset of modifier keys and the main key object.

    Args:
        keybind_string (str): The keybind string to parse.

    Returns:
        tuple[frozenset[pynput.keyboard.Key], pynput.keyboard.Key | pynput.keyboard.KeyCode]:
            A tuple where the first element is a frozenset of modifier key objects
            (from pynput.keyboard.Key) and the second element is the main key object
            (either pynput.keyboard.Key or pynput.keyboard.KeyCode).

    Raises:
        InvalidKeybindError: If the keybind string is invalid or contains unrecognized keys.
        PynputImportError: If pynput is not installed.
    """
    if not PYNPUT_AVAILABLE:
        raise PynputImportError("pynput library is required for key parsing.")

    if not keybind_string or not isinstance(keybind_string, str):
        raise InvalidKeybindError("Keybind string cannot be empty or non-string.")

    parts = [part.strip() for part in keybind_string.split('+')]
    if not parts:
        raise InvalidKeybindError("Keybind string cannot be empty after stripping.")

    modifiers = set()
    main_key = None
    parsed_keys = []

    for part in parts:
        if not part:
            raise InvalidKeybindError(f"Empty part found in keybind string: '{keybind_string}'")
        parsed_key = _parse_single_key(part)
        if parsed_key is None:
            raise InvalidKeybindError(f"Unrecognized key part: '{part}' in '{keybind_string}'")
        parsed_keys.append(parsed_key)

    # Identify modifiers and the main key (last non-modifier)
    potential_main_key = parsed_keys[-1]
    if potential_main_key in MODIFIER_MAP.values():
        # If the last key is a modifier, the combination is invalid (e.g., "ctrl+alt")
        # Exception: Allow single modifier keys if only one part was given (e.g. "ctrl")
        if len(parsed_keys) == 1:
             main_key = potential_main_key
             # No modifiers in this case
        else:
            raise InvalidKeybindError(f"Key combination must end with a non-modifier key: '{keybind_string}'")
    else:
        main_key = potential_main_key
        # All other parsed keys are modifiers
        for key in parsed_keys[:-1]:
            if key not in MODIFIER_MAP.values():
                raise InvalidKeybindError(f"Key '{key}' used as modifier is not a recognized modifier key in '{keybind_string}'")
            modifiers.add(key)

    if main_key is None:
         # This should theoretically not happen if logic above is correct, but safeguard
         raise InvalidKeybindError(f"Could not determine main key for '{keybind_string}'")

    logger.debug(f"Parsed '{keybind_string}' -> Modifiers: {modifiers}, Main Key: {main_key}")
    return (frozenset(modifiers), main_key)


# Example Usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO) # Use INFO for less verbose test output
    test_strings = [
        'f1', 'F12', 'cmd', 'ctrl', 'alt', 'shift', 'esc', 'space', 'enter', 'tab',
        'a', 'A', '1', '?',
        'fn', # Test fn separately
        'ctrl+c', 'alt+tab', 'cmd+shift+p', 'ctrl+alt+delete',
        'shift+a', 'ctrl+1',
        # Invalid cases
        'ctrl+', '+c', 'ctrl+alt', 'unknown+a', 'a+ctrl', ''
    ]
    if sys.platform != 'darwin':
        test_strings = [s for s in test_strings if 'cmd' not in s and 'fn' not in s]
        test_strings.append('ctrl+alt+del') # Windows equivalent often uses 'del'

    print("--- Testing Keybind Parser ---")
    for k_str in test_strings:
        try:
            modifiers, main = parse_keybind_string(k_str)
            mod_names = {m.name for m in modifiers} # Get names for printing
            print(f"'{k_str}' -> Modifiers: {mod_names or '{}'}, Main: {main} ({type(main).__name__})")
        except (InvalidKeybindError, PynputImportError) as e:
            print(f"'{k_str}' -> ERROR: {e}")
        except Exception as e:
             print(f"'{k_str}' -> UNEXPECTED ERROR: {type(e).__name__}: {e}")
             # import traceback
    print("--- Keybind Parser Test End ---")
