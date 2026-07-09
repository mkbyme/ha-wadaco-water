"""Setup and manage HomeAssistant sensor entities."""

import logging
from datetime import timedelta

from homeassistant.components.sensor import DOMAIN as ENTITY_DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import wadaco_water
from .const import (
    CONF_CUSTOMER_CODE,
    CONF_DEVICE_MANUFACTURER,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_SW_VERSION,
    CONF_ORG_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SUCCESS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
)
from .types import WADACO_SENSORS, WadacoSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Setup the sensor platform."""
    entry_config = hass.data[DOMAIN][entry.entry_id]

    api = wadaco_water.WadacoAPI(hass, True)
    device = WadacoDevice(entry_config, api)

    await device.async_create_coordinator(hass)

    async_add_entities(
        [WadacoSensor(device, description) for description in WADACO_SENSORS]
    )


class WadacoDevice:
    """Manages data fetching and coordinator for one customer account."""

    def __init__(self, dataset: dict, api: wadaco_water.WadacoAPI) -> None:
        self._name = f"{CONF_DEVICE_NAME}: {dataset[CONF_CUSTOMER_CODE]}"
        self._coordinator: DataUpdateCoordinator = None
        self.hass = api.hass
        self._org_code = dataset[CONF_ORG_CODE]
        self._customer_code = dataset[CONF_CUSTOMER_CODE]
        self._password = dataset[CONF_PASSWORD]
        self._api = api
        self._data = {"status": "unknown"}
        scan_hours = dataset.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
        self._scan_interval = timedelta(hours=scan_hours)

    async def _async_update(self):
        self._data = await self._api.request_update(
            self._org_code, self._customer_code, self._password
        )

        status = self._data.get("status")
        if status == CONF_SUCCESS:
            _LOGGER.info(
                "[Wadaco %s] Successfully fetched new data.", self._customer_code
            )
        else:
            _LOGGER.warning(
                "[Wadaco %s] Could not fetch data - status: %s",
                self._customer_code,
                status,
            )

    async def async_create_coordinator(self, hass: HomeAssistant) -> None:
        if self._coordinator:
            return

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self._customer_code}",
            update_method=self._async_update,
            update_interval=self._scan_interval,
        )
        await coordinator.async_config_entry_first_refresh()
        self._coordinator = coordinator

    @property
    def coordinator(self) -> DataUpdateCoordinator:
        return self._coordinator


class WadacoSensor(CoordinatorEntity, SensorEntity):
    """One sensor entity for a customer account."""

    def __init__(
        self,
        device: WadacoDevice,
        description: WadacoSensorEntityDescription,
    ):
        super().__init__(device.coordinator)
        self._device = device
        self._attr_name = f"{device._name} {description.name}"
        self._unique_id = f"{device._customer_code}_{description.key}".lower()
        self.entity_id = (
            f"{ENTITY_DOMAIN}.{device._customer_code}_{description.key}".lower()
        )
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self):
        data = self.entity_description.value_fn(self._device._data)

        if self.entity_description.dynamic_icon:
            self._attr_icon = data.get("info")

        return data.get("value")

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._device._data.get("status") != CONF_SUCCESS:
            return None
        data = self.entity_description.value_fn(self._device._data)
        attrs = {k: v for k, v in data.items() if k not in ("value", "info")}
        history_key = self.entity_description.history_key
        if history_key:
            history_data = self._device._data.get(history_key, {})
            attrs["history"] = history_data.get("value", [])
        return attrs if attrs else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._device._name,
            identifiers={(DOMAIN, self._device._customer_code)},
            manufacturer=CONF_DEVICE_MANUFACTURER,
            sw_version=CONF_DEVICE_SW_VERSION,
            model=CONF_DEVICE_MODEL,
        )

    @property
    def available(self) -> bool:
        return (
            self._device._data.get("status") == CONF_SUCCESS
            and self.native_value is not None
        )
