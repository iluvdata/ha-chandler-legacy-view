"""Helpers for updating the EVB019 brine tank level."""

from .models import BrineTank

_PACKET_LENGTH = 20
_DASHBOARD_FILL = 117
_COMMAND_OFFSET = 13
_SET_BRINE_TANK_COMMAND = 83


def create_brine_tank_settings_payload(tank: BrineTank) -> bytes:
    """Build the EVB019 Set Time payload for a local datetime."""

    payload = bytearray([_DASHBOARD_FILL] * _PACKET_LENGTH)
    payload[_COMMAND_OFFSET] = _SET_BRINE_TANK_COMMAND
    payload[_COMMAND_OFFSET + 1] = tank.regens_remaining
    payload[_COMMAND_OFFSET + 2] = tank.regens_remaining_low_salt
    payload[_COMMAND_OFFSET + 3] = tank.tank # tank size
    payload[_COMMAND_OFFSET + 4] = tank.fill_height
    return bytes(payload)
