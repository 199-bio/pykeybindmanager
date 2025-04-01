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


## Usage

For detailed usage instructions, code examples, and explanations of the different trigger types, please see the [Usage Guide (USAGE.md)](USAGE.md).

### Key Concepts (v0.2.2)

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
