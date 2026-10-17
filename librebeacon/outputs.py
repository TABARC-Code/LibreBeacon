"""Local accessibility outputs, entirely independent of Home Assistant."""
import subprocess
import sys
import threading


def beep():
    if sys.platform == 'win32':
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    else:
        # The application is primarily a Windows application; app-level bell is fallback.
        pass


def speak(text: str):
    """Offline Windows speech. Text is passed on stdin rather than embedded in PowerShell code."""
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
