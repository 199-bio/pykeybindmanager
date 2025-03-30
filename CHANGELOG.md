# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-03-31

### Added

-   Support for key combinations (e.g., "ctrl+alt+t", "cmd+s") via `parse_keybind_string`.
-   New `trigger_type` options for `KeybindManager`:
    -   `'toggle'`: Calls callback with `'press'` on each activation (for single keys or combinations).
    -   `'hold'`: Calls callback with `'press'` on key down and `'release'` on key up (for single keys or combinations).
-   `KeybindManager` now uses `on_release` events to track held keys for combinations and the `'hold'` trigger.

### Changed

-   Renamed original single/double press trigger logic to `trigger_type='double_press_toggle'`.
    -   Callback now receives `'single'` or `'double'` event types.
    -   This trigger type is now restricted to single keys (no modifiers) for simplicity and reliability.
-   The `on_activated` callback now consistently receives a string event type (`'press'`, `'release'`, `'single'`, `'double'`) as its only argument.
-   `KeybindManager` initialization now takes `keybind_definition` (the tuple output from `parse_keybind_string`) and `trigger_type` as required arguments.
-   Reduced logging verbosity. Default behavior is no output unless the application configures the `logging` module. Kept essential `INFO` and `ERROR`/`WARNING` logs.
-   Updated internal modifier key tracking.

### Fixed

-   Ensured `_pressed_keys` set is cleared on listener start and stop.

## [0.1.0] - 2025-03-31

### Added

-   Initial release of `pykeybindmanager`.
-   `KeybindManager` class to listen for single/double key presses of a *single* key using `pynput`.
-   `parse_keybind_string` helper function to convert single key names (e.g., 'f1', 'cmd', 'fn') to `pynput` objects.
-   `play_sound_file` utility to play 'start' and 'stop' notification sounds using platform-specific players.
-   Custom exceptions (`KeybindManagerError`, `ListenerError`, `PermissionError`, `InvalidKeybindError`, `PynputImportError`).
-   Basic logging configuration.
-   Support for macOS 'fn' key.
-   Included 'doubleping.wav' and 'singleping.wav' sound files.
