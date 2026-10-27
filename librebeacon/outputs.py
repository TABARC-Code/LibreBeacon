"""Small local sounds and Windows speech. Keep these offline and optional."""
from __future__ import annotations
import subprocess
import sys
import threading

# Short patterns, not sirens. Quiet rooms, shared rooms, hearing aids: test the
# actual device. Volume is controlled by Windows, not by these numbers.
SOUND_PATTERNS = {
    'Gentle': ((520, 140),),
    'Standard': ((740, 180), (740, 180)),
    'Distinct': ((560, 130), (820, 210), (560, 130)),
}


def tone_pattern(style: str) -> tuple[tuple[int, int], ...]:
    if style not in SOUND_PATTERNS:
        raise ValueError('Select a supported sound style')
    return SOUND_PATTERNS[style]


def beep(style: str = 'Standard') -> bool:
    """Play a bounded local sound on Windows; return False on unsupported systems.

    Don't try to fake success. An audio driver or muted PC can still be silent.
    """
    pattern = tone_pattern(style)
    if sys.platform != 'win32':
        return False
    import winsound
    for frequency, duration in pattern:
        winsound.Beep(frequency, duration)
    return True


def start_beep(style: str = 'Standard'):
    """Don't block the Tk event loop whilst Windows plays the pattern."""
    tone_pattern(style)
    threading.Thread(target=beep, args=(style,), daemon=True).start()


def speak(text: str):
    """Offline Windows speech. Pipe words to stdin, not into PowerShell code."""
    if sys.platform != 'win32':
        return
    command = [
        'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        'Add-Type -AssemblyName System.Speech; '
        '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
        '$s.Speak([Console]::In.ReadToEnd())'
    ]
    subprocess.run(command, input=text, text=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=20, check=False,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def start_speech(text: str):
    threading.Thread(target=speak, args=(text,), daemon=True).start()
