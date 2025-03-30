# PyKeybindManager

A simple Python module for listening to specific keyboard keybinds (single keys or combinations) using the `pynput` library. Supports toggle, double-press toggle, and press-and-hold activation types, suitable for applications like dictation control. Includes optional sound feedback.

## Features

-   Listen for specific keyboard keys (e.g., `F1`, `fn`) or combinations (e.g., `Ctrl+C`, `Cmd+Shift+P`).
-   Supports multiple activation modes via `trigger_type`:
    -   `'toggle'`: Activate on each press of the key/combination.
    -   `'double_press_toggle'`: Activate differently for single vs. double presses (single keys only).
    -   `'hold'`: Activate on press and again on release of the key/combination.
-   Run the listener in a background thread.
-   Trigger a user-defined callback function with the event type (`'press'`, `'release'`, `'single'`, `'double'`).
-   Provide optional sound feedback ('start'/'stop' sounds) using platform-specific methods.
-   Helper function (`parse_keybind_string`) to easily convert keybind strings (e.g., `"alt+t"`, `"f1"`) into the required internal format.
-   Handles macOS-specific considerations like Input Monitoring permissions and the 'fn' key.
-   Minimal logging by default; relies on the application to configure logging levels.

## Requirements

-   Python 3.x
-   `pynput` library (`pip install pynput`)

**Platform Notes:**

-   **macOS:** Requires "Input Monitoring" permission for the application/terminal running the script. The script attempts to handle the `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` environment variable needed by `pynput` on macOS. The `fn` key is supported. `cmd` key is mapped correctly.
-   **Linux:** May require root privileges depending on the environment, or the user needs to be in the `input` group. `meta` key is mapped to `ctrl`.
-   **Windows:** Should generally work without special permissions. `meta` key is mapped to `ctrl`.
    -   **Sound Playback:** Relies on common system utilities (`afplay` on macOS, `winsound` on Windows, `aplay`/`paplay`/`mplayer`/`mpg123` on Linux). If these are not available, sound playback might fail silently or log a warning.

## Installation

Install the package from PyPI using pip:

```bash
pip install pykeybindmanager
```

This will also automatically install the required `pynput` dependency.

### Development Installation

If you have cloned the repository and want to install it for development (e.g., to make changes):

```bash
# Navigate to the repository root directory (where pyproject.toml is)
pip install -e .
```

```bash
pip install pynput
```

## Usage

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

```

### Key Concepts (v0.2.0)

-   **`parse_keybind_string(keybind_string)`**:
    -   Input: A string like `"f1"`, `"ctrl+c"`, `"alt+shift+t"`, `"fn"`. Uses `+` as a separator.
    -   Output: A tuple `(frozenset[modifier_keys], main_key)`. Modifiers are `pynput.keyboard.Key` objects (e.g., `Key.ctrl`). The main key is a `Key` or `KeyCode` object.
-   **`KeybindManager(keybind_definition, on_activated, trigger_type, on_error=None, double_press_threshold=0.3)`**:
    -   `keybind_definition`: The tuple returned by `parse_keybind_string`.
    -   `on_activated`: Your callback function. Receives one argument: the event type string (`'press'`, `'release'`, `'single'`, or `'double'`).
    -   `trigger_type`: Specifies the activation behavior. Must be one of:
        -   `'toggle'`: Callback gets `'press'` on activation. Good for start/stop actions triggered by the same key/combo.
        -   `'double_press_toggle'`: Callback gets `'single'` or `'double'`. **Only valid for single keys (no modifiers)**. Good for distinguishing single vs. double taps.
        -   `'hold'`: Callback gets `'press'` when the key/combo goes down, and `'release'` when the main key comes up. Ideal for push-to-talk/record.
    -   `on_error`: Optional function to handle errors (like permission issues). Receives the exception object.
    -   `double_press_threshold`: Time in seconds for `'double_press_toggle'` detection (default: 0.3s).
-   **`manager.start_listener()`**: Starts listening in the background.
-   **`manager.stop_listener()`**: Stops the background listener thread.
-   **`play_sound_file(sound_type, blocking=False)`**: Plays a sound.
    -   `sound_type`: Either `'start'` (plays `doubleping.wav`) or `'stop'` (plays `singleping.wav`).
    -   `blocking`: If `True`, waits for the sound to finish. Defaults to `False`.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
