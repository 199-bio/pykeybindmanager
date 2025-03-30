import sys
import os
import logging
import threading
import time
import traceback
from .exceptions import KeybindManagerError, ListenerError, PermissionError, PynputImportError, InvalidKeybindError
from .keys import MODIFIER_MAP # Import modifier map

# Setup logger for this module
logger = logging.getLogger(__name__)

# Attempt to import pynput
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    keyboard = None
    # Raise PynputImportError later if needed

class KeybindManager:
    """
    Listens for a specific keyboard keybind (single key or combination)
    using pynput and triggers callbacks based on specified trigger type.

    Requires the 'pynput' library.
    On macOS, requires Input Monitoring permission.
    """

    DEFAULT_DOUBLE_PRESS_THRESHOLD_S = 0.3 # Default threshold in seconds
    VALID_TRIGGER_TYPES = {'toggle', 'double_press_toggle', 'hold'}

    def __init__(self, keybind_definition, on_activated, trigger_type, on_error=None, double_press_threshold=DEFAULT_DOUBLE_PRESS_THRESHOLD_S):
        """
        Initializes the KeybindManager.

        Args:
            keybind_definition (tuple): The parsed keybind tuple from `parse_keybind_string`:
                                        (frozenset[modifier_keys], main_key).
            on_activated (callable): Function called when the keybind is activated.
                                     Receives event type: 'press', 'release', 'single', 'double'.
            trigger_type (str): How the keybind triggers the callback. Must be one of:
                                'toggle': Callback(event='press') on each press.
                                'double_press_toggle': Callback(event='single'/'double') on press
                                                       (only valid for single keys, no modifiers).
                                'hold': Callback(event='press') on press, Callback(event='release') on release.
            on_error (callable, optional): Function called on errors (e.g., permissions).
                                           Receives the exception object. Defaults to logging the error.
            double_press_threshold (float, optional): Time in seconds for double press detection.
                                                      Defaults to 0.3s.

        Raises:
            PynputImportError: If pynput is not installed.
            InvalidKeybindError: If keybind_definition is invalid.
            ValueError: If trigger_type is invalid or incompatible with keybind_definition.
        """
        if not PYNPUT_AVAILABLE:
            raise PynputImportError("pynput library is required but not found.")

        # Validate keybind_definition structure
        if not isinstance(keybind_definition, tuple) or len(keybind_definition) != 2 or \
           not isinstance(keybind_definition[0], frozenset) or \
           not isinstance(keybind_definition[1], (keyboard.Key, keyboard.KeyCode)):
            raise InvalidKeybindError("keybind_definition must be a tuple (frozenset[modifiers], main_key). Use parse_keybind_string.")

        self.target_modifiers, self.target_main_key = keybind_definition

        # Validate trigger_type
        if trigger_type not in self.VALID_TRIGGER_TYPES:
            raise ValueError(f"Invalid trigger_type '{trigger_type}'. Must be one of {self.VALID_TRIGGER_TYPES}")
        self.trigger_type = trigger_type

        # Validate trigger_type compatibility
        if self.trigger_type == 'double_press_toggle' and self.target_modifiers:
            raise ValueError("trigger_type 'double_press_toggle' is only valid for single keys (no modifiers).")

        self.on_activated = on_activated
        self.on_error = on_error or (lambda e: logger.error(f"KeybindManager Error: {e}")) # Default error handler
        self.double_press_threshold = double_press_threshold

        self._pressed_keys = set() # Track currently held keys
        self._last_press_time = 0 # For double press detection
        self._listener_thread = None
        self._listener_instance = None
        self._stop_event = threading.Event()

        # Reduced logging
        logger.info(f"KeybindManager initialized for: Modifiers={{{', '.join(m.name for m in self.target_modifiers)}}}, Key={self.target_main_key}, Trigger='{self.trigger_type}'")

    def start_listener(self):
        """Starts the keyboard listener in a separate thread."""
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("Listener thread already running.")
            return

        self._stop_event.clear()
        self._pressed_keys.clear() # Clear state on start
        try:
            self._listener_thread = threading.Thread(target=self._run_listener, daemon=True)
            self._listener_thread.start()
            logger.info("Keyboard listener thread started.")
        except Exception as e:
            error = ListenerError(f"Failed to start listener thread: {e}")
            logger.error(error) # Log error
            # logger.error(traceback.format_exc()) # Avoid verbose trace unless debugging
            self.on_error(error)

    def stop_listener(self):
        """Stops the keyboard listener thread."""
        if not self._listener_thread or not self._listener_thread.is_alive():
            # logger.info("Listener thread not running.") # Reduce noise
            return

        logger.info("Stopping keyboard listener thread...")
        self._stop_event.set()

        if self._listener_instance:
            try:
                self._listener_instance.stop()
            except Exception as e:
                 logger.error(f"Error stopping pynput listener instance: {e}")

        self._listener_thread.join(timeout=2.0)

        if self._listener_thread.is_alive():
            logger.warning("Listener thread did not stop gracefully.")
        else:
            logger.info("Listener thread stopped.")

        self._listener_thread = None
        self._listener_instance = None
        self._pressed_keys.clear() # Clear state on stop

    def _run_listener(self):
        """The target function for the listener thread."""
        try:
            # Set macOS env var if needed (only log if setting it)
            if sys.platform == 'darwin' and 'OBJC_DISABLE_INITIALIZE_FORK_SAFETY' not in os.environ:
                os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
                logger.info("Set OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES for macOS")

            # logger.debug("pynput listener starting...") # Reduce noise
            # Use on_press and on_release
            with keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release) as self._listener_instance:
                self._stop_event.wait()
                # logger.debug("Stop event received, exiting listener loop.") # Reduce noise

        except OSError as e:
            # Handle permission errors specifically
            if sys.platform == 'darwin' and ("Operation not permitted" in str(e) or "permission" in str(e).lower()):
                error = PermissionError("Input Monitoring permission denied for pynput.")
                logger.error(error)
                self.on_error(error)
            else:
                error = ListenerError(f"Unhandled OSError in listener: {e}")
                logger.error(error)
                # logger.error(traceback.format_exc()) # Avoid verbose trace
                self.on_error(error)
        except Exception as e:
            error = ListenerError(f"Unexpected error in listener thread: {e}")
            logger.error(error)
            # logger.error(traceback.format_exc()) # Avoid verbose trace
            self.on_error(error)
        finally:
             # logger.debug("pynput listener thread finished.") # Reduce noise
             self._listener_instance = None

    def _get_currently_pressed_modifiers(self):
        """Returns the set of currently pressed known modifier keys."""
        # Intersect pressed keys with the values from MODIFIER_MAP
        return self._pressed_keys.intersection(MODIFIER_MAP.values())

    def _on_key_press(self, key):
        """Callback executed by pynput when a key is pressed."""
        if self._stop_event.is_set():
            return False # Stop the listener

        # Add key to the set of pressed keys *before* checking
        # Use normalized key representation if possible (pynput might handle this)
        self._pressed_keys.add(key)

        try:
            # Check if the pressed key is the main target key
            if key == self.target_main_key:
                # Check if the currently pressed modifiers match the target modifiers
                current_modifiers = self._get_currently_pressed_modifiers()

                # We need exact match: all target modifiers must be pressed,
                # and no *other* known modifiers should be pressed.
                if current_modifiers == self.target_modifiers:
                    # --- Keybind Match Found ---
                    current_time = time.time()

                    if self.trigger_type == 'toggle':
                        self._trigger_callback('press')

                    elif self.trigger_type == 'double_press_toggle':
                        # This type is only allowed for single keys (checked in __init__)
                        time_since_last = current_time - self._last_press_time
                        press_type = 'single'
                        if time_since_last < self.double_press_threshold:
                            press_type = 'double'
                        self._last_press_time = current_time # Update time *only* on match
                        self._trigger_callback(press_type)

                    elif self.trigger_type == 'hold':
                        self._trigger_callback('press')
                        # Reset last press time for hold to avoid double-press interference if reused
                        self._last_press_time = 0

        except Exception as e:
            logger.error(f"Error during key press processing: {e}")
            # logger.error(traceback.format_exc()) # Avoid verbose trace

        return True # Continue listening

    def _on_key_release(self, key):
        """Callback executed by pynput when a key is released."""
        if self._stop_event.is_set():
            return False # Stop the listener

        try:
            # Check if the released key is the main target key for the 'hold' trigger
            if self.trigger_type == 'hold' and key == self.target_main_key:
                 # Check if the target modifiers were held *just before* release.
                 # This is tricky because the modifier might be released slightly before/after.
                 # A simpler check: assume if the main key is released, the 'hold' ends.
                 # We don't need to re-verify modifiers on release for 'hold'.
                 self._trigger_callback('release')

        except Exception as e:
            logger.error(f"Error during key release processing: {e}")
            # logger.error(traceback.format_exc()) # Avoid verbose trace
        finally:
            # Always remove the key from the set on release
            self._pressed_keys.discard(key) # Use discard to avoid KeyError if release comes without press

        return True # Continue listening

    def _trigger_callback(self, event_type):
        """Safely triggers the user's on_activated callback."""
        if self.on_activated:
            try:
                # logger.debug(f"Triggering callback with event: {event_type}") # Reduce noise
                self.on_activated(event_type)
            except Exception as cb_e:
                 logger.error(f"Error in on_activated callback: {cb_e}")
                 # logger.error(traceback.format_exc()) # Avoid verbose trace
                 # Optionally call self.on_error here if callback errors should be reported
                 # self.on_error(ListenerError(f"Error in on_activated callback: {cb_e}"))


# Example Usage (for testing the module directly)
if __name__ == '__main__':
    # Configure logging for the example (shows INFO level from manager)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Import parse function here for example usage
    from .keys import parse_keybind_string

    print("--- Testing PyKeybindManager v0.2.0 ---")

    # --- Test Case Callbacks ---
    def handle_toggle_event(event):
        print(f"CALLBACK [Toggle]: Event='{event}'") # Should only receive 'press'

    def handle_double_toggle_event(event):
        print(f"CALLBACK [Double Toggle]: Event='{event}'") # Receives 'single' or 'double'

    def handle_hold_event(event):
        print(f"CALLBACK [Hold]: Event='{event}'") # Receives 'press' or 'release'

    def handle_generic_error(err):
        print(f"CALLBACK [Error]: {type(err).__name__} - {err}")

    # --- Test Cases ---
    test_cases = [
        # Keybind String, Trigger Type, Callback Function
        ("f1", 'toggle', handle_toggle_event),
        ("f2", 'double_press_toggle', handle_double_toggle_event),
        ("fn", 'hold', handle_hold_event), # macOS specific 'fn' hold
        ("ctrl+c", 'toggle', handle_toggle_event), # Combination toggle
        ("alt+shift+1", 'toggle', handle_toggle_event), # Multi-modifier combo
        # ("ctrl+f3", 'double_press_toggle', handle_double_toggle_event), # INVALID: Double press on combo
    ]
    if sys.platform != 'darwin':
         test_cases = [tc for tc in test_cases if 'fn' not in tc[0] and 'cmd' not in tc[0]]
         test_cases.append(("ctrl+alt+del", 'toggle', handle_toggle_event)) # Example for other platforms

    managers = []
    print("\nInitializing Managers...")
    for kb_str, trigger, callback in test_cases:
        try:
            print(f"Setting up: '{kb_str}', Trigger: '{trigger}'")
            definition = parse_keybind_string(kb_str)
            manager = KeybindManager(
                keybind_definition=definition,
                on_activated=callback,
                trigger_type=trigger,
                on_error=handle_generic_error
            )
            managers.append(manager)
        except (PynputImportError, InvalidKeybindError, ValueError) as e:
            print(f"  ERROR setting up '{kb_str}': {e}")
        except Exception as e:
            print(f"  UNEXPECTED ERROR setting up '{kb_str}': {type(e).__name__} - {e}")

    if not managers:
        print("\nNo managers were successfully initialized. Exiting.")
        sys.exit(1)

    print("\nStarting all listeners... Press defined keys/combos. Press Ctrl+C in terminal to stop.")
    for m in managers:
        m.start_listener()

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received.")
    finally:
        print("Stopping all listeners...")
        for m in managers:
            m.stop_listener()
        print("All listeners stopped.")

    print("\n--- PyKeybindManager Test End ---")
