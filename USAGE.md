# PyKeybindManager Usage Guide

This guide provides detailed instructions and examples on how to use the `pykeybindmanager` module to listen for keyboard keybinds in your Python applications.

## 1. Installation

First, ensure you have installed the package:

```bash
pip install pykeybindmanager
```

This also installs the necessary `pynput` dependency.

## 2. Basic Setup: Imports and Logging

Start by importing the required components from the module:

```python
import time
import logging
import sys
from pykeybindmanager import KeybindManager, parse_keybind_string, play_sound_file
from pykeybindmanager.exceptions import PermissionError, PynputImportError, InvalidKeybindError, ListenerError
```

-   `KeybindManager`: The main class for managing a specific keybind listener.
-   `parse_keybind_string`: A helper function to convert user-friendly strings (like `"ctrl+d"`) into the format needed by `KeybindManager`.
-   `play_sound_file`: An optional utility to play simple audio feedback.
-   Exceptions: Specific error types raised by the module (e.g., `PermissionError` on macOS if permissions are missing).

**Optional Logging:**

The library uses Python's standard `logging` module but attaches a `NullHandler` by default. This means it won't produce any output unless you configure logging in your application. To see informational messages or errors from the library, configure logging:

```python
# Configure basic logging to show INFO level messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# You can also get a specific logger instance if needed
log = logging.getLogger(__name__) # Logger for your application
lib_log = logging.getLogger('pykeybindmanager') # Logger for the library itself
# lib_log.setLevel(logging.DEBUG) # Uncomment to see detailed debug messages from the library
```

## 3. Defining Callback Functions

The core of using `KeybindManager` is providing a callback function that gets executed when your defined keybind is activated. This function receives a single argument: `event_type`.

-   **`event_type` (str):** Indicates how the keybind was triggered. The possible values depend on the `trigger_type` you set when creating the `KeybindManager`:
    -   For `trigger_type='toggle'`: `event_type` will always be `'press'`.
    -   For `trigger_type='double_press_toggle'`: `event_type` will be `'single'` or `'double'`.
    -   For `trigger_type='hold'`: `event_type` will be `'press'` when the keybind is pressed down, and `'release'` when the main key of the keybind is released.

Here are example callback functions for a hypothetical dictation application:

```python
# --- Application State (Example for Dictation) ---
is_recording = False

# --- Callback for 'toggle' ---
def handle_toggle_activation(event_type):
    """Handles 'toggle' type activation (e.g., press Ctrl+D to start/stop)."""
    global is_recording
    # 'toggle' only sends 'press' events
    if event_type == 'press':
        is_recording = not is_recording
        status = "STARTED" if is_recording else "STOPPED"
        sound = 'start' if is_recording else 'stop'
        play_sound_file(sound) # Optional sound feedback
        logging.info(f"Toggle Keybind Pressed: Recording {status}")

# --- Callback for 'double_press_toggle' ---
def handle_double_press_activation(event_type):
    """Handles 'double_press_toggle' type activation (e.g., double-press F1 to start/stop)."""
    global is_recording
    # Distinguish between single and double press
    if event_type == 'double':
        is_recording = not is_recording
        status = "STARTED" if is_recording else "STOPPED"
        sound = 'start' if is_recording else 'stop'
        play_sound_file(sound)
        logging.info(f"Double Press Detected: Recording {status}")
    elif event_type == 'single':
        logging.info("Single press detected (ignored by this handler).")

# --- Callback for 'hold' ---
def handle_hold_activation(event_type):
    """Handles 'hold' type activation (e.g., hold 'fn' to record)."""
    global is_recording
    # Handle press and release events separately
    if event_type == 'press':
        if not is_recording:
            is_recording = True
            play_sound_file('start')
            logging.info("Hold Key Pressed: Recording STARTED")
    elif event_type == 'release':
        if is_recording:
            is_recording = False
            play_sound_file('stop')
            logging.info("Hold Key Released: Recording STOPPED")

# --- Optional Error Callback ---
def handle_error(exception):
    """Handles errors reported by the KeybindManager."""
    logging.error(f"KeybindManager Error: {type(exception).__name__} - {exception}")
    if isinstance(exception, PermissionError):
        logging.error("Please ensure the application has Input Monitoring permissions (macOS) or necessary privileges.")
    # You might want to add logic here to notify the user or exit gracefully
```

## 4. Parsing Keybind Strings

Before creating a `KeybindManager`, you need to define the keybind itself. The `parse_keybind_string` function converts human-readable strings into the internal format required by the manager.

-   **Input:** A string representing the keybind. Use `+` to separate modifiers and the main key. Modifiers should come first.
    -   Examples: `"f1"`, `"ctrl+c"`, `"alt+shift+t"`, `"cmd+s"` (Cmd is macOS specific), `"fn"` (macOS specific).
    -   Known modifiers: `ctrl`, `alt`, `shift`, `cmd` (macOS) / `ctrl` (Win/Linux), `meta` (alias for cmd/ctrl).
-   **Output:** A tuple `(frozenset[modifier_keys], main_key)`.

```python
# Example parsing:
kb1_str = "ctrl+d"
kb1_def = parse_keybind_string(kb1_str) # -> (frozenset({Key.ctrl}), KeyCode(char='d'))

kb2_str = "f1"
kb2_def = parse_keybind_string(kb2_str) # -> (frozenset(), Key.f1)

kb3_str = "fn" # macOS specific
if sys.platform == 'darwin':
    try:
        kb3_def = parse_keybind_string(kb3_str) # -> (frozenset(), KeyCode(vk=179))
    except InvalidKeybindError as e:
        logging.warning(f"Could not parse 'fn': {e}")
```

## 5. Initializing KeybindManager

Create an instance of `KeybindManager` for each keybind you want to listen for.

```python
manager = KeybindManager(
    keybind_definition=kb_def,      # The tuple from parse_keybind_string
    on_activated=callback_func,     # Your callback function
    trigger_type=trigger_str,       # 'toggle', 'double_press_toggle', or 'hold'
    on_error=error_handler_func,    # Optional: Your error handling function
    double_press_threshold=0.3      # Optional: Time (sec) for double press detection
)
```

**Understanding `trigger_type`:**

-   **`'toggle'`:**
    -   Activates on each press of the key or combination.
    -   Callback receives `event_type='press'`.
    -   Suitable for actions that cycle through states (e.g., start/stop, on/off) with the same keybind.
    -   Works with single keys and combinations.

-   **`'double_press_toggle'`:**
    -   Distinguishes between a single press and a rapid double press of the *same key*.
    -   Callback receives `event_type='single'` or `event_type='double'`.
    -   **Constraint:** Only works for *single keys* (no modifiers). Using it with a combination like `"ctrl+a"` will raise a `ValueError`.
    -   Useful when you want different actions for a tap vs. a double-tap.

-   **`'hold'`:**
    -   Activates when the keybind is pressed down *and* again when the main key is released.
    -   Callback receives `event_type='press'` on key down and `event_type='release'` on key up.
    -   Ideal for "push-to-talk" or "hold-to-record" functionality.
    -   Works with single keys and combinations. The `'release'` event triggers when the *main key* (not modifiers) is released, assuming the modifiers were held during the press.

## 6. Starting and Stopping the Listener

Once managers are created, you need to start them. The library uses a shared background listener thread, which is started when the first manager calls `start_listener()`.

```python
# Create a list to hold your managers
managers = []
# ... (initialize your KeybindManager instances and add them to the list) ...

# Start all listeners
logging.info("Starting listeners...")
for manager in managers:
    manager.start_listener()

# Keep your main script alive
# The listener runs in a background thread, so your main thread needs to keep running.
try:
    while True:
        time.sleep(1) # Or do other work
except KeyboardInterrupt:
    logging.info("Stopping listeners...")
finally:
    # Stop listeners gracefully
    for manager in managers:
        manager.stop_listener()
    logging.info("All listeners stopped.")

```

-   `manager.start_listener()`: Registers the manager to receive events from the shared background listener. Starts the listener if it's not already running.
-   `manager.stop_listener()`: Deregisters the manager. Stops the shared listener if this was the last active manager. It's important to call this for cleanup.

## 7. Error Handling

Provide an `on_error` callback function during `KeybindManager` initialization to handle potential issues, such as:

-   `PermissionError`: On macOS, if Input Monitoring permission is not granted.
-   `ListenerError`: General errors related to the underlying `pynput` listener.

Your `on_error` function will receive the exception object as an argument.

## 8. Sound Feedback

The `play_sound_file(sound_type, blocking=False)` function provides simple audio cues.

-   `sound_type`: Either `'start'` (plays `doubleping.wav`) or `'stop'` (plays `singleping.wav`). These files are included with the package.
-   `blocking`: If `True`, the function waits for the sound to finish playing. Defaults to `False` (plays asynchronously in a separate thread).

## Full Example Code

This example demonstrates setting up managers for all three trigger types.

```python
import time
import logging
import sys
from pykeybindmanager import KeybindManager, parse_keybind_string, play_sound_file
from pykeybindmanager.exceptions import PermissionError, PynputImportError, InvalidKeybindError, ListenerError

# --- Application State (Example for Dictation) ---
is_recording = False

# --- Configure Logging (Optional) ---
# The library uses NullHandler by default. Configure if you want to see logs.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__) # Get logger for application messages

# --- Callback Functions ---

def handle_toggle_activation(event_type):
    """Handles 'toggle' type activation (e.g., press Ctrl+D to start/stop)."""
    global is_recording
    if event_type == 'press':
        is_recording = not is_recording
        status = "STARTED" if is_recording else "STOPPED"
        sound = 'start' if is_recording else 'stop'
        play_sound_file(sound)
        log.info(f"Toggle Keybind Pressed: Recording {status}")

def handle_double_press_activation(event_type):
    """Handles 'double_press_toggle' type activation (e.g., double-press F1 to start/stop)."""
    global is_recording
    # Example: Only toggle on double press
    if event_type == 'double':
        is_recording = not is_recording
        status = "STARTED" if is_recording else "STOPPED"
        sound = 'start' if is_recording else 'stop'
        play_sound_file(sound)
        log.info(f"Double Press Detected: Recording {status}")
    elif event_type == 'single':
        log.info("Single press detected (ignored by this handler).")

def handle_hold_activation(event_type):
    """Handles 'hold' type activation (e.g., hold 'fn' to record)."""
    global is_recording
    if event_type == 'press':
        if not is_recording:
            is_recording = True
            play_sound_file('start')
            log.info("Hold Key Pressed: Recording STARTED")
    elif event_type == 'release':
        if is_recording:
            is_recording = False
            play_sound_file('stop')
            log.info("Hold Key Released: Recording STOPPED")

def handle_error(exception):
    """Handles errors from the KeybindManager."""
    log.error(f"KeybindManager Error: {type(exception).__name__} - {exception}")
    if isinstance(exception, PermissionError):
        log.error("Please ensure the application has Input Monitoring permissions (macOS) or necessary privileges.")
    # Consider exiting or notifying the user based on the error

# --- Main Logic ---
if __name__ == "__main__":
    managers = []
    try:
        # --- Define Keybinds ---
        # Example 1: Toggle recording with Ctrl+D
        kb1_str = "ctrl+d"
        kb1_def = parse_keybind_string(kb1_str)
        manager1 = KeybindManager(kb1_def, handle_toggle_activation, trigger_type='toggle', on_error=handle_error)
        managers.append(manager1)
        log.info(f"Registered '{kb1_str}' with trigger 'toggle'")

        # Example 2: Double-press F1 to toggle recording
        kb2_str = "f1"
        kb2_def = parse_keybind_string(kb2_str)
        manager2 = KeybindManager(kb2_def, handle_double_press_activation, trigger_type='double_press_toggle', on_error=handle_error)
        managers.append(manager2)
        log.info(f"Registered '{kb2_str}' with trigger 'double_press_toggle'")

        # Example 3: Hold 'fn' key to record (macOS specific)
        if sys.platform == 'darwin':
            kb3_str = "fn"
            try:
                kb3_def = parse_keybind_string(kb3_str)
                manager3 = KeybindManager(kb3_def, handle_hold_activation, trigger_type='hold', on_error=handle_error)
                managers.append(manager3)
                log.info(f"Registered '{kb3_str}' with trigger 'hold'")
            except InvalidKeybindError as e:
                 log.warning(f"Could not register 'fn' key: {e}") # Might fail if pynput doesn't map vk 179

        # --- Start Listeners ---
        log.info("Starting listeners... Press Ctrl+C to exit.")
        for manager in managers:
            manager.start_listener()

        # Keep the main script running
        while True:
            time.sleep(1)

    except (PynputImportError, InvalidKeybindError, ValueError, ListenerError) as e:
        log.error(f"Initialization Error: {e}")
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received. Stopping listeners...")
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # --- Stop Listeners Gracefully ---
        for manager in managers:
            manager.stop_listener()
        log.info("All listeners stopped.")