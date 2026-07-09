from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume

from .const import (
    ID_BILL_AMOUNT,
    ID_BILL_HISTORY,
    ID_CONSUMPTION,
    ID_FROM_DATE,
    ID_LATEST_UPDATE,
    ID_METER_INDEX,
    ID_PAYMENT_STATUS,
    ID_TO_DATE,
)


@dataclass
class WadacoRequiredKeysMixin:
    value_fn: Callable[[Any], Any]


@dataclass
class WadacoSensorEntityDescription(SensorEntityDescription, WadacoRequiredKeysMixin):
    dynamic_icon: None | bool = False
    history_key: str | None = None


WADACO_SENSORS: tuple[WadacoSensorEntityDescription, ...] = (
    WadacoSensorEntityDescription(
        key=ID_CONSUMPTION,
        name="Tiêu thụ nước tháng này",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda data: data[ID_CONSUMPTION],
    ),
    WadacoSensorEntityDescription(
        key=ID_METER_INDEX,
        name="Chỉ số đồng hồ nước",
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data[ID_METER_INDEX],
        history_key=ID_BILL_HISTORY,
    ),
    WadacoSensorEntityDescription(
        key=ID_BILL_AMOUNT,
        name="Tiền hóa đơn nước gần nhất",
        icon="mdi:cash-multiple",
        native_unit_of_measurement="VNĐ",
        value_fn=lambda data: data[ID_BILL_AMOUNT],
        dynamic_icon=True,
    ),
    WadacoSensorEntityDescription(
        key=ID_PAYMENT_STATUS,
        name="Trạng thái thanh toán",
        icon="mdi:comment-question-outline",
        value_fn=lambda data: data[ID_PAYMENT_STATUS],
        dynamic_icon=True,
    ),
    WadacoSensorEntityDescription(
        key=ID_FROM_DATE,
        name="Ngày đầu kỳ",
        icon="mdi:calendar-clock",
        value_fn=lambda data: data[ID_FROM_DATE],
    ),
    WadacoSensorEntityDescription(
        key=ID_TO_DATE,
        name="Ngày chốt kỳ gần nhất",
        icon="mdi:calendar-clock",
        value_fn=lambda data: data[ID_TO_DATE],
    ),
    WadacoSensorEntityDescription(
        key=ID_LATEST_UPDATE,
        name="Lần cập nhật cuối",
        icon="mdi:calendar-check",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data[ID_LATEST_UPDATE],
    ),
)
