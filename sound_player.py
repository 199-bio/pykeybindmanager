import os
import sys
import logging
import traceback
import subprocess
import threading
import tempfile
import importlib.resources
import atexit

# Setup logger for this module
logger = logging.getLogger(__name__)

# Define sound file names relative to the 'sounds' subdirectory
SOUND_START = "doubleping.wav"
SOUND_STOP = "singleping.wav"

# Keep track of created temporary files to clean up on exit
_temp_sound_files = []

def _cleanup_temp_files():
    """Delete temporary sound files created during the session."""
    logger.debug(f"Cleaning up {len(_temp_sound_files)} temporary sound files...")
    for temp_file_path in _temp_sound_files:
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.debug(f"Removed temporary file: {temp_file_path}")
        except OSError as e:
            logger.error(f"Error removing temporary file {temp_file_path}: {e}")
    _temp_sound_files.clear()

# Register the cleanup function to run at Python exit
atexit.register(_cleanup_temp_files)


def _get_sound_path(sound_name):
    """
    Gets a reliable path to a sound file for playback.
    Reads the sound data from package resources and writes it to a
    persistent temporary file. Returns the path to the temporary file.
    """
    try:
        # Read the binary data from the package resource
        # Ensure the package name is correct, especially if run as script
        package_name = __package__ if __package__ else os.path.basename(os.path.dirname(__file__))
        sound_data = importlib.resources.read_binary(package_name + '.sounds', sound_name)

        # Create a named temporary file that persists until deleted
        # Suffix helps identify the file type if needed
        # Use a more specific prefix for easier identification
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(sound_name)[1], prefix="pykeybindsnd_") as temp_file:
            temp_file.write(sound_data)
            temp_file_path = temp_file.name
            _temp_sound_files.append(temp_file_path) # Track for cleanup
            logger.debug(f"Created temporary sound file for '{sound_name}': {temp_file_path}")
            return temp_file_path

    except (FileNotFoundError, TypeError, ModuleNotFoundError, Exception) as e:
        # Catch ModuleNotFoundError if package resolution fails
        logger.error(f"Could not read or write sound resource '{sound_name}': {e}")
        return None


def play_sound_file(sound_type, blocking=False):
    """Play a predefined sound ('start' or 'stop') using platform-specific methods.

    Args:
        sound_type (str): Either 'start' or 'stop'.
        blocking (bool): Whether to wait for sound to finish playing.

    Returns:
        bool: True if successful, False otherwise.
    """
    sound_file_name = None
    if sound_type == 'start':
        sound_file_name = SOUND_START
    elif sound_type == 'stop':
        sound_file_name = SOUND_STOP
    else:
        logger.warning(f"Invalid sound_type specified: {sound_type}")
        return False

    # Get the path to the (potentially temporary) sound file
    sound_file_path = _get_sound_path(sound_file_name)

    if not sound_file_path:
        logger.warning(f"Could not resolve path for sound: {sound_file_name}")
        return False

    try:
        logger.info(f"Playing sound '{sound_type}': {sound_file_path}")

        if blocking:
            # Play sound in blocking mode
            return _play_sound_blocking(sound_file_path)
        else:
            # Play sound in non-blocking mode
            # Pass the path, not the name, as it might be a temp file path
            sound_thread = threading.Thread(target=_play_sound_blocking, args=(sound_file_path,))
            sound_thread.daemon = True
            sound_thread.start()
            return True
    except Exception as e:
        logger.error(f"Error playing sound: {e}")
        logger.error(traceback.format_exc())
        return False

def _play_sound_blocking(sound_file_path):
    """Internal method to play sound in blocking mode"""
    # Check existence again just before playing
    if not os.path.exists(sound_file_path):
        logger.error(f"Sound file disappeared before playback: {sound_file_path}")
        return False
    try:
        if sys.platform == 'darwin':  # macOS
            try:
                # First try afplay (preferred)
                logger.debug(f"Attempting to play via afplay: {sound_file_path}")
                # Check path existence one last time right before calling
                if not os.path.exists(sound_file_path):
                    raise FileNotFoundError(f"Temporary sound file not found immediately before playback: {sound_file_path}")

                # Use check=False to inspect result even on failure, capture output
                result = subprocess.run(['afplay', sound_file_path], check=False,
                                        capture_output=True, text=True, timeout=5)
                # Log results regardless of success
                logger.debug(f"afplay result: code={result.returncode}, stdout='{result.stdout[:100]}...', stderr='{result.stderr[:100]}...'") # Log truncated output
                # Raise specific error if afplay failed
                if result.returncode != 0:
                    # Log the full error before raising
                    logger.error(f"afplay failed! Code: {result.returncode}, Stderr: {result.stderr}")
                    raise subprocess.SubprocessError(f"afplay failed with code {result.returncode}")
                return True # Return True only if afplay succeeded
            except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.warning(f"afplay failed: {e}, trying fallback")
                # Fallback to say (makes a beep if sound file can't be played)
                try:
                    subprocess.run(['say', '-v', 'Alex', '[[volm 0.0]] beep'], check=False, # Play silent beep as fallback
                                 stderr=subprocess.PIPE, stdout=subprocess.PIPE, timeout=2)
                    return True # Return true even if fallback used, as *something* happened
                except Exception as e2:
                    logger.error(f"All macOS sound methods failed: {e2}")
                    return False
        elif sys.platform == 'win32':  # Windows
            try:
                import winsound
                winsound.PlaySound(sound_file_path, winsound.SND_FILENAME | winsound.SND_NODEFAULT) # Add NODEFAULT
                return True
            except Exception as e:
                logger.warning(f"Windows sound playback failed: {e}")
                # Fallback to beep
                try:
                    winsound.Beep(1000, 300)  # 1000 Hz for 300ms
                    return True
                except Exception as e2:
                    logger.error(f"All Windows sound methods failed: {e2}")
                    return False
        else:  # Linux or other
            # Try to use aplay, paplay, or mplayer in sequence
            players = [
                ['aplay', '-q', sound_file_path], # Add -q for quiet
                ['paplay', sound_file_path],
                ['mplayer', '-really-quiet', sound_file_path], # Add quiet flag
                ['mpg123', '-q', sound_file_path] # Add -q for quiet
            ]

            for player_cmd in players:
                try:
                    logger.debug(f"Attempting to play via {' '.join(player_cmd)}")
                    result = subprocess.run(player_cmd, check=False, capture_output=True, text=True, timeout=5)
                    logger.debug(f"{player_cmd[0]} result: code={result.returncode}, stdout='{result.stdout}', stderr='{result.stderr}'")
                    if result.returncode == 0:
                        return True
                except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                     logger.debug(f"{player_cmd[0]} failed: {e}")
                     continue # Try next player

            logger.warning("No suitable audio player found on this platform")
            return False
    except Exception as e:
        logger.error(f"Error in _play_sound_blocking: {e}")
        logger.error(traceback.format_exc())
        return False

# For testing purposes
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("--- Testing Sound Player ---")
    print("Attempting to play 'start' sound...")
    play_sound_file('start', blocking=True)
    print("Attempting to play 'stop' sound...")
    play_sound_file('stop', blocking=True)
    print("Attempting to play invalid sound...")
    play_sound_file('invalid', blocking=True)
    print("--- Sound Player Test End ---")
    # Explicitly call cleanup for testing if needed, though atexit should handle it
    # _cleanup_temp_files()
