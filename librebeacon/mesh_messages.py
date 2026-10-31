"""Small Meshtastic messages. Radio airtime isn't free, even when the software is.

One short message per approved node. Nobody needs a medical essay on a radio.
The reference is for tracing a request, NOT a two-way acknowledgement yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from secrets import token_hex

# Conservative upper limit, lower than the Android composer allowance.
# Count UTF-8 bytes, never Python characters. Keep this boring and bounded.
MESH_TEXT_MAX_BYTES = 180
_REFERENCE = re.compile(r"LB-[0-9A-F]{16}\Z")


@dataclass(frozen=True)
class MeshText:
    kind: str
    reference: str
    body: str


def new_reference() -> str:
    return "LB-" + token_hex(8).upper()


def build_mesh_message(kind: str, *, reference: str | None = None,
                       include_value: bool = False, mmol: float | None = None) -> MeshText:
    """Create a labelled test or a privacy-minimised supplementary alert.

    No recipient names, locations or glucose measurements unless explicitly
    chosen elsewhere. Be careful with 'helpful' additions: the mesh is shared
    infrastructure, and an overlong message may simply never leave the radio.
    """
    if kind not in ('test', 'critical_low'):
        raise ValueError('Unknown mesh message type')
    if type(include_value) is not bool:
        raise ValueError('Glucose privacy choice must be true or false')
    ref = new_reference() if reference is None else reference
    if not isinstance(ref, str) or not _REFERENCE.fullmatch(ref):
        raise ValueError('Invalid mesh message reference')
    if kind == 'test':
        if include_value or mmol is not None:
            raise ValueError('Test messages cannot contain glucose measurements')
        body = f'TEST ONLY - LibreBeacon radio check {ref}. No emergency. Please confirm with the sender.'
    else:
        body = (f'LibreBeacon ALERT {ref}: Please check your nominated contact now. '
                'Use your agreed plan. Reply using your usual contact method.')
        if include_value:
            if type(mmol) not in (int, float) or not isfinite(mmol) or not 0 < mmol <= 40:
                raise ValueError('A valid glucose measurement is required for this message')
            body += f' Glucose: {mmol:.1f} mmol/L.'
    if len(body.encode('utf-8')) > MESH_TEXT_MAX_BYTES:
        raise ValueError('Meshtastic message exceeds the conservative size limit')
    return MeshText(kind=kind, reference=ref, body=body)


def check_mesh_text(message: MeshText, kind: str) -> MeshText:
    """A preview must be exactly what gets sent, not a second edited string."""
    if not isinstance(message, MeshText) or message.kind != kind:
        raise ValueError('A matching prepared message is required')
    expected = message.reference
    if not _REFERENCE.fullmatch(expected):
        raise ValueError('Invalid mesh message reference')
    if not isinstance(message.body, str) or len(message.body.encode('utf-8')) > MESH_TEXT_MAX_BYTES:
        raise ValueError('Meshtastic message size invalid')
    # Do not allow arbitrary radio text to be slipped in via a preview object.
    if kind == 'test' and message != build_mesh_message('test', reference=expected):
        raise ValueError('Unrecognised test message')
    if kind == 'critical_low':
        raise ValueError('Critical-low alerts must be constructed at dispatch')
    return message
