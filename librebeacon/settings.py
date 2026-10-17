"""Settings contain no passwords or medical history."""
from dataclasses import dataclass, asdict, fields, field
from pathlib import Path
import json
import os

APP_DIR = Path(os.getenv('LOCALAPPDATA', Path.home() / '.config')) / 'LibreBeacon'
CONFIG_FILE = APP_DIR / 'settings.json'
SECRET_SERVICE = 'LibreBeacon.HomeAssistant'
SECRET_USER = 'HomeAssistantToken'

@dataclass
class Settings:
    ha_url: str = ''
    glucose_entity: str = ''
    timestamp_entity: str = ''
    visual_script: str = ''
    contact_script: str = ''
    contact_label: str = ''
    enabled: bool = False
    enable_sound: bool = True
    enable_visual: bool = True
    enable_speech: bool = False
    enable_ha_visual: bool = False
    enable_contacts: bool = False
    contact_consent: bool = False
    low_mmol: str = ''
    high_mmol: str = ''
    freshness_minutes: int = 10
    poll_seconds: int = 60
    cooldown_minutes: int = 15
    large_text: bool = True
    # Unset until a person chooses a value with appropriate clinical guidance.
    critical_low_mmol: str = ''
    enable_emergency_contacts: bool = False
    emergency_contact_consent: bool = False
    include_glucose_in_messages: bool = False
    emergency_routes: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> 'Settings':
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding='utf-8'))
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')
        os.replace(tmp, path)
        # Private on POSIX. Windows permissions come from the user's profile ACL.
        if os.name == 'posix':
            os.chmod(path, 0o600)


def save_token(token: str) -> None:
    import keyring
    keyring.set_password(SECRET_SERVICE, SECRET_USER, token)


def load_token() -> str:
    token = os.getenv('LIBREBEACON_HA_TOKEN')
    if token:
        return token
    try:
        import keyring
        return keyring.get_password(SECRET_SERVICE, SECRET_USER) or ''
    except Exception:
        return ''
