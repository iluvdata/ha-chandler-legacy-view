"""Helpers for updating Home Assistant's device registry."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DISCOVERY_VIA_DEVICE_ID, DOMAIN


def async_update_device_serial_number(
    hass: HomeAssistant, address: str, serial_number: str | None
) -> None:
    """Update the stored serial number for a valve if it has changed."""

    device_registry, device_entry = _async_get_device_registry_and_device_id(
        hass, address
    )
    if device_entry is None:
        return

    if device_entry.serial_number == serial_number:
        return

    device_registry.async_update_device(device_entry.id, serial_number=serial_number)


def async_update_device_sw_version(
    hass: HomeAssistant, address: str, sw_version: str | None
) -> None:
    """Update the stored firmware version for a valve if it has changed."""

    device_registry, device_entry = _async_get_device_registry_and_device_id(
        hass, address
    )
    if device_entry is None:
        return

    if device_entry.sw_version == sw_version:
        return

    device_registry.async_update_device(device_entry.id, sw_version=sw_version)


def _async_get_config_entry_id(hass: HomeAssistant) -> str | None:
    if config_entries := hass.config_entries.async_entries(DOMAIN, False, False):
        if config_entry := config_entries.pop():
            return config_entry.entry_id
    return None


def _async_get_device_registry_and_device_id(
    hass: HomeAssistant, id: str
) -> tuple[dr.DeviceRegistry, dr.DeviceEntry | None]:
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, id), _async_get_config_entry_id(hass)
    )
    return device_registry, device_entry


def async_get_discovery_device_id(hass: HomeAssistant) -> str | None:
    """Get the device id to (temporarily) comply with HA device registry changes."""

    _, device_entry = _async_get_device_registry_and_device_id(
        hass, DISCOVERY_VIA_DEVICE_ID
    )
    if device_entry is not None:
        return device_entry.id

    return None
