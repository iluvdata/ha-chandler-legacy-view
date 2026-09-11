"""Select entities for Chandler Legacy View."""

import logging

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connection import ValveConnection, ValveConnectionManager
from .const import DATA_CONNECTION_MANAGER, DATA_DISCOVERY_MANAGER, DOMAIN
from .discovery import BLUETOOTH_LOST_CHANGES, ValveDiscoveryManager
from .entity import ChandlerValveEntity
from .models import BrineTankSize, ValveAdvertisement, ValveDashboardData

_LOGGER = logging.getLogger(__name__)


class BrineTankType(ChandlerValveEntity, SelectEntity):
    """Select enitty for the brine tank type."""

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection):
        """Initialize a select entity."""
        super().__init__(advertisement)
        self._attr_icon = "mdi:cylinder"
        self._connection = connection
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_unique_id = f"{advertisement.address}_brine_tank_type"
        self._attr_name = f"{self._attr_name} Brine Tank Size"
        self._remove_dashboard_listener: CALLBACK_TYPE | None = None
        self._update_from_dashboard(connection.dashboard_data, write_state=False)
        self._remove_dashboard_listener = connection.add_dashboard_listener(
            self._handle_dashboard_update
        )
        self._attr_options = [tank.name for tank in BrineTankSize]

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when the entity is removed."""

        await super().async_will_remove_from_hass()
        if self._remove_dashboard_listener is not None:
            self._remove_dashboard_listener()
            self._remove_dashboard_listener = None

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
        self._attr_current_option = BrineTankSize(dashboard.brine_tank.tank).name
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
        self._attr_name = f"{self._attr_name} Brine Tank Size"

    async def async_select_option(self, value: str) -> None:
        """Update the configured persistent polling interval."""

        tank = self._connection.dashboard_data.brine_tank
        tank.tank = BrineTankSize[value]
        tank.fill_height = BrineTankSize[value].get_default_fill_height
        self._attr_current_option = value
        _LOGGER.debug("Updating brine tank size %s: %s", value, tank)
        await self._connection.async_update_tank_settings(tank)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up persistent poll interval numbers for Chandler valves."""

    entry_data = hass.data[DOMAIN][entry.entry_id]
    discovery_manager: ValveDiscoveryManager = entry_data[DATA_DISCOVERY_MANAGER]
    connection_manager: ValveConnectionManager = entry_data[DATA_CONNECTION_MANAGER]

    entities: dict[str, BrineTankType] = {}

    def _ensure_brine_tank_type_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[
        BrineTankType | None,
        list[BrineTankType],
    ]:
        entity = entities.get(advertisement.address)
        new_entities: list[BrineTankType] = []

        if entity is None:
            connection = connection_manager.get_connection(advertisement.address)
            if connection is None:
                _LOGGER.debug(
                    "Delaying brine tank type entity creation for %s; connection not ready",
                    advertisement.address,
                )
                return None, new_entities

            if connection.dashboard_data is None:
                _LOGGER.debug(
                    "Delaying brine tank type creation for %s; databoard not loaded",
                    advertisement.address,
                )
                return None, new_entities

            if connection.dashboard_data.brine_tank is None:
                _LOGGER.debug(
                    "Not loading brine tanke type entity %s; not supported by valve",
                    advertisement.address,
                )
                return None, new_entities

            entity = BrineTankType(advertisement, connection)
            entities[advertisement.address] = entity
            new_entities.append(entity)

        return entity, new_entities

    initial_entities: list[BrineTankType] = []
    for advertisement in discovery_manager.devices.values():
        _, new_entities = _ensure_brine_tank_type_entity(advertisement)
        initial_entities.extend(new_entities)

    if initial_entities:
        async_add_entities(initial_entities)

    @callback
    def _handle_discovery(
        advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        if change in BLUETOOTH_LOST_CHANGES:
            entity = entities.get(advertisement.address)
            if entity is not None:
                entity.async_handle_bluetooth_update(advertisement, change)
            return

        entity, new_entities = _ensure_brine_tank_type_entity(advertisement)

        if entity is None:
            return

        if new_entities:
            async_add_entities(new_entities)

        entity.async_handle_bluetooth_update(advertisement, change)

    remove_listener = discovery_manager.async_add_listener(_handle_discovery)
    entry.async_on_unload(remove_listener)
