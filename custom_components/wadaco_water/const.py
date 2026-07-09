"""Constants for the Wadaco Nước Sạch integration."""

from datetime import timedelta

# Water meters are hand-read once a month (around the 4th-6th), so there is no
# point polling as aggressively as an electricity meter integration would.
DEFAULT_SCAN_INTERVAL_HOURS = 12
DEFAULT_SCAN_INTERVAL = timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS)

CONF_SCAN_INTERVAL = "scan_interval"

DOMAIN = "wadaco_water"

BASE_URL = "https://myservice.citywork.vn"
URL_LOGIN = f"{BASE_URL}/Mobile/LoginByUserCode"
URL_INVOICES = f"{BASE_URL}/InVoices/findInVoicesByTime"

CONF_DEVICE_NAME = "Wadaco Nước Sạch"
CONF_DEVICE_MODEL = "Wadaco Water Monitor"
CONF_DEVICE_MANUFACTURER = "Wadaco"
CONF_DEVICE_SW_VERSION = "1.0.0"

CONF_ORG_CODE = "org_code"
CONF_CUSTOMER_CODE = "customer_code"
CONF_PASSWORD = "password"

CONF_SUCCESS = "success"
CONF_EMPTY = "empty"
CONF_ERR_CANNOT_CONNECT = "cannot_connect"
CONF_ERR_INVALID_AUTH = "invalid_auth"
CONF_ERR_UNKNOWN = "unknown"

ID_CONSUMPTION = "water_consumption"
ID_METER_INDEX = "meter_index"
ID_BILL_AMOUNT = "bill_amount"
ID_PAYMENT_STATUS = "payment_status"
ID_FROM_DATE = "from_date"
ID_TO_DATE = "to_date"
ID_LATEST_UPDATE = "latest_update"
ID_BILL_HISTORY = "bill_history"

STATUS_PAID = "Đã thanh toán"
STATUS_UNPAID = "Chưa thanh toán"
