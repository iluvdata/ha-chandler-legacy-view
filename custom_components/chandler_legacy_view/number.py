"""Number entities for configuring Chandler valves."""

import logging
from math import floor

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfMass, UnitOfTime
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connection import ValveConnection, ValveConnectionManager
from .const import (
    DATA_CONNECTION_MANAGER,
    DATA_DISCOVERY_MANAGER,
    DOMAIN,
    MAX_PERSISTENT_POLL_INTERVAL_SECONDS,
    MIN_PERSISTENT_POLL_INTERVAL_SECONDS,
)
from .discovery import BLUETOOTH_LOST_CHANGES, ValveDiscoveryManager
from .entity import ChandlerValveEntity
from .models import BrineTankSize, ValveAdvertisement, ValveDashboardData

_LOGGER = logging.getLogger(__name__)


class ValvePersistentPollIntervalNumber(ChandlerValveEntity, NumberEntity):
    """Configure the polling interval used while a persistent connection is active."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = MIN_PERSISTENT_POLL_INTERVAL_SECONDS
    _attr_native_max_value = MAX_PERSISTENT_POLL_INTERVAL_SECONDS
    _attr_native_step = 1.0

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
        connection_manager: ValveConnectionManager,
    ) -> None:
        """Initialize entity."""
        super().__init__(advertisement)
        self._connection = connection
        self._connection_manager = connection_manager
        self._attr_unique_id = f"{advertisement.address}_persistent_poll_interval"
        self._attr_name = f"{self._attr_name} Persistent Poll Interval"
        self._attr_available = True
        self._attr_native_value = connection.persistent_poll_interval

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for the valve."""

        if change in BLUETOOTH_LOST_CHANGES:
            self._attr_available = False
        else:
            self.async_update_from_advertisement(advertisement)
            self._attr_available = True

        self._attr_native_value = self._connection.persistent_poll_interval
        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store the latest advertisement details for the valve."""

        super().async_update_from_advertisement(advertisement)
        self._attr_name = f"{self._attr_name} Persistent Poll Interval"

    async def async_set_native_value(self, value: float) -> None:
        """Update the configured persistent polling interval."""

        self._attr_native_value = (
            await self._connection_manager.async_set_persistent_poll_interval(
                self._connection.address, value
            )
        )
        if self.hass is not None:
            self.async_write_ha_state()


class BrineTankSaltLevel(ChandlerValveEntity, NumberEntity):
    """Configure the polling interval used while a persistent connection is active."""

    _attr_native_unit_of_measurement = UnitOfMass.POUNDS
    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_icon = "mdi:shaker-outline"
    _attr_native_min_value = 0
    _attr_native_step = 1

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
    ) -> None:
        """Initialize entity."""
        super().__init__(advertisement)
        self._connection = connection
        self._attr_translation_key = "brine_tank_salt_level"
        self._attr_unique_id = f"{advertisement.address}_{self._attr_translation_key}"
        self._attr_name = f"{self._attr_name} Brine Tank Salt Level"
        self._remove_dashboard_listener: CALLBACK_TYPE | None = None
        self._update_from_dashboard(connection.dashboard_data, write_state=False)
        self._remove_dashboard_listener = connection.add_dashboard_listener(
            self._handle_dashboard_update
        )

    @callback
    def _handle_dashboard_update(self, dashboard: ValveDashboardData | None) -> None:
        """Handle updates from the dashboard poller."""

        self._update_from_dashboard(dashboard, write_state=True)

    @callback
    def _update_from_dashboard(
        self, dashboard: ValveDashboardData | None, write_state: bool
    ) -> None:
        """Update entity with dashboard data."""
        if dashboard is None:
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = dashboard.brine_tank.salt_remaining
        self._attr_native_max_value = floor(dashboard.brine_tank.total_salt)
        self._attr_extra_state_attributes = {
            "regens_remaining": dashboard.brine_tank.regens_remaining,
            "remaining_salt_percent": f"{round(dashboard.brine_tank.salt_remaining_percent * 100)}%",
        }
        if write_state and self.hass is not None:
            self.async_write_ha_state()

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for the valve."""

        if change in BLUETOOTH_LOST_CHANGES:
            self._attr_available = False
        else:
            self.async_update_from_advertisement(advertisement)
            self._attr_available = True

        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store the latest advertisement details for the valve."""

        super().async_update_from_advertisement(advertisement)
        self._attr_name = f"{self._attr_name} Brine Tank Salt Level"

    async def async_set_native_value(self, value: float) -> None:
        """Update the configured persistent polling interval."""

        tank = self._connection.dashboard_data.brine_tank
        tank.set_salt_level(value)
        _LOGGER.debug("Updating brine tank salt level %i: %s", value, tank)
        await self._connection.async_update_tank_settings(tank)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when the entity is removed."""

        await super().async_will_remove_from_hass()
        if self._remove_dashboard_listener is not None:
            self._remove_dashboard_listener()
            self._remove_dashboard_listener = None


class BrineTankFillLevel(ChandlerValveEntity, NumberEntity):
    """Configure the polling interval used while a persistent connection is active."""

    _attr_native_unit_of_measurement = UnitOfLength.INCHES
    _attr_icon = "mdi:basket-fill"
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
    ) -> None:
        """Initialize entity."""
        super().__init__(advertisement)
        self._connection = connection
        self._attr_translation_key = "brine_tank_fill_level"
        self._attr_unique_id = f"{advertisement.address}_{self._attr_translation_key}"
        self._attr_name = f"{self._attr_name} Brine Tank Fill Height"
        self._remove_dashboard_listener: CALLBACK_TYPE | None = None
        self._update_from_dashboard(connection.dashboard_data, write_state=False)
        self._remove_dashboard_listener = connection.add_dashboard_listener(
            self._handle_dashboard_update
        )

    @callback
    def _handle_dashboard_update(self, dashboard: ValveDashboardData | None) -> None:
        """Handle updates from the dashboard poller."""

        self._update_from_dashboard(dashboard, write_state=True)

    @callback
    def _update_from_dashboard(
        self, dashboard: ValveDashboardData | None, write_state: bool
    ) -> None:
        """Update entity with dashboard data."""
        if dashboard is None:
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = dashboard.brine_tank.fill_height
        self._attr_native_max_value = BrineTankSize(
            dashboard.brine_tank.tank
        ).get_max_fill_height
        if write_state and self.hass is not None:
            self.async_write_ha_state()

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for the valve."""

        if change in BLUETOOTH_LOST_CHANGES:
            self._attr_available = False
        else:
            self.async_update_from_advertisement(advertisement)
            self._attr_available = True

        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store the latest advertisement details for the valve."""

        super().async_update_from_advertisement(advertisement)
        self._attr_name = f"{self._attr_name} Brine Tank Salt Level"

    async def async_set_native_value(self, value: float) -> None:
        """Update the configured persistent polling interval."""

        tank = self._connection.dashboard_data.brine_tank
        tank.fill_height = int(value)
        _LOGGER.debug("Updating brine tank fill height %i: %s", value, tank)
        await self._connection.async_update_tank_settings(tank)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when the entity is removed."""

        await super().async_will_remove_from_hass()
        if self._remove_dashboard_listener is not None:
            self._remove_dashboard_listener()
            self._remove_dashboard_listener = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up persistent poll interval numbers for Chandler valves."""

    entry_data = hass.data[DOMAIN][entry.entry_id]
    discovery_manager: ValveDiscoveryManager = entry_data[DATA_DISCOVERY_MANAGER]
    connection_manager: ValveConnectionManager = entry_data[DATA_CONNECTION_MANAGER]

    persistent_poll_interval_entities: dict[str, ValvePersistentPollIntervalNumber] = {}
    brine_tank_entities: dict[str, tuple[BrineTankFillLevel, BrineTankSaltLevel]] = {}

    def _ensure_persistent_poll_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[
        ValvePersistentPollIntervalNumber | None,
        list[ValvePersistentPollIntervalNumber],
    ]:
        entity = persistent_poll_interval_entities.get(advertisement.address)
        new_entities: list[ValvePersistentPollIntervalNumber] = []

        if entity is None:
            connection = connection_manager.get_connection(advertisement.address)
            if connection is None:
                _LOGGER.debug(
                    "Delaying persistent poll interval entity creation for %s; connection not ready",
                    advertisement.address,
                )
                return None, new_entities

            entity = ValvePersistentPollIntervalNumber(
                advertisement, connection, connection_manager
            )
            persistent_poll_interval_entities[advertisement.address] = entity
            new_entities.append(entity)

        return entity, new_entities

    def _ensure_brine_tank_entities(
        advertisement: ValveAdvertisement,
    ) -> tuple[
        BrineTankFillLevel | None,
        BrineTankSaltLevel | None,
        list[BrineTankSaltLevel | BrineTankFillLevel],
    ]:
        fill_level_entity, salt_level_entity = brine_tank_entities.get(
            advertisement.address, (None, None)
        )
        new_entities: list[BrineTankSaltLevel | BrineTankFillLevel] = []

        if fill_level_entity is None:
            connection = connection_manager.get_connection(advertisement.address)
            if connection is None:
                _LOGGER.debug(
                    "Delaying brine tank entity creation for %s; connection not ready",
                    advertisement.address,
                )
                return None, None, new_entities

            if connection.dashboard_data is None:
                _LOGGER.debug(
                    "Delaying brine tank entity creation for %s; dashboard not populated",
                    advertisement.address,
                )
                return None, None, new_entities

            if connection.dashboard_data.brine_tank is None:
                _LOGGER.debug(
                    "Not creating a brine tank entity for %s;  Valve doesn't support brine tank levels",
                    advertisement.address,
                )
                return None, None, new_entities

            fill_level_entity = BrineTankFillLevel(advertisement, connection)
            salt_level_entity = BrineTankSaltLevel(advertisement, connection)
            brine_tank_entities[advertisement.address] = (
                fill_level_entity,
                salt_level_entity,
            )
            new_entities.append(fill_level_entity)
            new_entities.append(salt_level_entity)

        return fill_level_entity, salt_level_entity, new_entities

    initial_entities: list[ValvePersistentPollIntervalNumber | BrineTankSaltLevel] = []
    for advertisement in discovery_manager.devices.values():
        _, new_entities = _ensure_persistent_poll_entity(advertisement)
        initial_entities.extend(new_entities)
        _, _, new_entities = _ensure_brine_tank_entities(advertisement)
        initial_entities.extend(new_entities)

    if initial_entities:
        async_add_entities(initial_entities)

    @callback
    def _handle_discovery(
        advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        if change in BLUETOOTH_LOST_CHANGES:
            entity = persistent_poll_interval_entities.get(advertisement.address)
            if entity is not None:
                entity.async_handle_bluetooth_update(advertisement, change)
            fill_level_entity, salt_level_entity = brine_tank_entities.get(
                advertisement.address
            )
            if fill_level_entity is not None:
                fill_level_entity.async_handle_bluetooth_update(advertisement, change)
            if salt_level_entity is not None:
                salt_level_entity.async_handle_bluetooth_update(advertisement, change)
            return

        entity, new_entities = _ensure_persistent_poll_entity(advertisement)
        if entity is None:
            return

        if new_entities:
            async_add_entities(new_entities)

        entity.async_handle_bluetooth_update(advertisement, change)

        fill_level_entity, salt_level_entity, new_entities = (
            _ensure_brine_tank_entities(advertisement)
        )

        if new_entities:
            async_add_entities(new_entities)

    remove_listener = discovery_manager.async_add_listener(_handle_discovery)
    entry.async_on_unload(remove_listener)
