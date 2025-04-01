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

# --- Shared Listener State ---
_shared_listener_instance = None
_shared_listener_thread = None
_active_managers = []
_pressed_keys = set()
_manager_lock = threading.Lock()
_stop_event = threading.Event()
# --- End Shared Listener State ---

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
        self._last_press_time = 0 # For double press detection (still instance-specific)

        # Reduced logging
        logger.info(f"KeybindManager initialized for: Modifiers={{{', '.join(m.name for m in self.target_modifiers)}}}, Key={self.target_main_key}, Trigger='{self.trigger_type}'")

    def start_listener(self):
        """Registers this manager to receive events from the shared listener."""
        global _active_managers, _manager_lock
        with _manager_lock:
            if self not in _active_managers:
                _active_managers.append(self)
                logger.debug(f"Manager for {self.target_main_key} added to active list.")
                # Start the shared listener only if this is the first active manager
                if len(_active_managers) == 1:
                    _start_shared_listener()
            else:
                 logger.warning(f"Manager for {self.target_main_key} already active.")
    def stop_listener(self):
        """Deregisters this manager from the shared listener."""
        global _active_managers, _manager_lock
        with _manager_lock:
            if self in _active_managers:
                _active_managers.remove(self)
                logger.debug(f"Manager for {self.target_main_key} removed from active list.")
                # Stop the shared listener only if this was the last active manager
                if not _active_managers:
                    _stop_shared_listener()
    # _run_listener method removed as it's handled by the shared listener thread
    # _get_currently_pressed_modifiers removed, logic incorporated into _check_and_handle_press
    def _check_and_handle_press(self, key, current_pressed_keys_snapshot):
        """
        Checks if the pressed key matches this manager's keybind, given the
        current global state of pressed keys, and triggers the callback if needed.
        Called by the shared listener's _on_shared_press.
        """
        try:
            # Check if the pressed key is the main target key for this manager
            if key == self.target_main_key:
                # Extract currently pressed *known* modifiers from the global snapshot
                current_modifiers = current_pressed_keys_snapshot.intersection(MODIFIER_MAP.values())

                # We need exact match: all target modifiers must be pressed,
                # and no *other* known modifiers should be pressed.
                if current_modifiers == self.target_modifiers:
                    # --- Keybind Match Found for this manager ---
                    current_time = time.time()

                    if self.trigger_type == 'toggle':
                        self._trigger_callback('press')

                    elif self.trigger_type == 'double_press_toggle':
                        # This type is only allowed for single keys (checked in __init__)
                        time_since_last = current_time - self._last_press_time
                        press_type = 'single'
                        if time_since_last < self.double_press_threshold:
                            press_type = 'double'
                        # Update instance-specific last press time *only* on match
                        self._last_press_time = current_time
                        self._trigger_callback(press_type)

                    elif self.trigger_type == 'hold':
                        self._trigger_callback('press')
                        # Reset instance-specific last press time for hold
                        self._last_press_time = 0

        except Exception as e:
            # Log error specific to this manager's handling
            logger.error(f"Error during key press check for {self.target_main_key}: {e}")
    def _check_and_handle_release(self, key):
        """
        Checks if the released key matches this manager's target key for 'hold'
        trigger and triggers the callback if needed.
        Called by the shared listener's _on_shared_release.
        """
        try:
            # Check if the released key is the main target key for the 'hold' trigger
            if self.trigger_type == 'hold' and key == self.target_main_key:
                 # The shared listener handles tracking pressed keys globally.
                 # We only need to check if this manager cares about this release.
                 # We assume the modifiers *were* correct when the press happened.
                 self._trigger_callback('release')

        except Exception as e:
            # Log error specific to this manager's handling
            logger.error(f"Error during key release check for {self.target_main_key}: {e}")

        # Note: The global _pressed_keys set is managed by _on_shared_release
    def _trigger_callback(self, event_type):
        """Safely triggers the user's on_activated callback."""
        if self.on_activated:
            try:
                self.on_activated(event_type)
            except Exception as cb_e:
                 logger.error(f"Error in on_activated callback: {cb_e}")
                 # Optionally call self.on_error here if callback errors should be reported

# --- Shared Listener Control Functions ---

def _start_shared_listener():
    """Starts the shared pynput listener if not already running."""
    global _shared_listener_instance, _shared_listener_thread, _stop_event, _pressed_keys
    if _shared_listener_thread and _shared_listener_thread.is_alive():
        return # Already running

    logger.info("Starting shared keyboard listener thread...")
    _stop_event.clear()
    _pressed_keys.clear() # Reset global state on start

    def listener_thread_target():
        global _shared_listener_instance
        try:
            # Set macOS env var if needed
            if sys.platform == 'darwin' and 'OBJC_DISABLE_INITIALIZE_FORK_SAFETY' not in os.environ:
                os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
                logger.info("Set OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES for macOS (Shared Listener)")

            with keyboard.Listener(on_press=_on_shared_press, on_release=_on_shared_release) as listener:
                _shared_listener_instance = listener
                _stop_event.wait() # Wait until stop is requested
        except OSError as e:
             # Handle permission errors specifically
            if sys.platform == 'darwin' and ("Operation not permitted" in str(e) or "permission" in str(e).lower()):
                error = PermissionError("Input Monitoring permission denied for pynput (Shared Listener).")
                logger.error(error)
                # Propagate error to all active managers? Difficult. Log is best effort.
                # Consider adding a global error callback?
            else:
                error = ListenerError(f"Unhandled OSError in shared listener: {e}")
                logger.error(error)
            # Attempt to notify managers?
            with _manager_lock:
                for manager in _active_managers:
                    manager.on_error(error) # Notify active managers
        except Exception as e:
            error = ListenerError(f"Unexpected error in shared listener thread: {e}")
            logger.error(error)
            # Attempt to notify managers?
            with _manager_lock:
                for manager in _active_managers:
                    manager.on_error(error) # Notify active managers
        finally:
            logger.debug("Shared pynput listener thread finished.")
            _shared_listener_instance = None # Clear instance on exit

    _shared_listener_thread = threading.Thread(target=listener_thread_target, daemon=True)
    _shared_listener_thread.start()

def _stop_shared_listener():
    """Stops the shared pynput listener if running."""
    global _shared_listener_instance, _shared_listener_thread, _stop_event
    if not _shared_listener_thread or not _shared_listener_thread.is_alive():
        return # Not running

    logger.info("Stopping shared keyboard listener thread...")
    _stop_event.set()

    if _shared_listener_instance:
        try:
            # Attempt to stop the listener instance directly
            # This might help unblock the thread if it's stuck
            _shared_listener_instance.stop()
        except Exception as e:
            logger.error(f"Error stopping shared pynput listener instance: {e}")

    _shared_listener_thread.join(timeout=2.0)

    if _shared_listener_thread.is_alive():
        logger.warning("Shared listener thread did not stop gracefully.")
    else:
        logger.info("Shared listener thread stopped.")

    _shared_listener_thread = None
    _shared_listener_instance = None
    _pressed_keys.clear() # Reset global state on stop

# --- Shared Listener Callbacks ---

def _on_shared_press(key):
    """Callback for key presses from the shared listener."""
    if _stop_event.is_set():
        return False # Stop listener

    _pressed_keys.add(key) # Update global state *before* dispatching

    with _manager_lock:
        # Iterate over a copy in case managers deregister during iteration
        managers_to_notify = list(_active_managers)

    # Perform checks outside the lock to avoid holding it during callbacks
    current_pressed_keys_snapshot = frozenset(_pressed_keys) # Pass immutable snapshot
    for manager in managers_to_notify:
        try:
            manager._check_and_handle_press(key, current_pressed_keys_snapshot)
        except Exception as e:
            logger.error(f"Error dispatching press event to manager {manager}: {e}")

    return True # Continue listening

def _on_shared_release(key):
    """Callback for key releases from the shared listener."""
    if _stop_event.is_set():
        return False # Stop listener

    with _manager_lock:
        # Iterate over a copy
        managers_to_notify = list(_active_managers)

    # Perform checks outside the lock
    for manager in managers_to_notify:
         try:
            manager._check_and_handle_release(key)
         except Exception as e:
            logger.error(f"Error dispatching release event to manager {manager}: {e}")

    # Update global state *after* dispatching release checks
    _pressed_keys.discard(key)

    return True # Continue listening

# --- End Shared Listener Components ---

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
