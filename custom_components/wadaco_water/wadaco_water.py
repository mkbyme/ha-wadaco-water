"""Wadaco Nước Sạch API client.

The customer-care portal (cskh.wadaco.com.vn) only uses its
`Mobile/LoginByUserCode` call to validate a customer's password; the actual
consumption/invoice data behind `InVoices/findInVoicesByTime` requires no
auth token at all (confirmed from captured traffic), so there is no session
or token-refresh logic to maintain here — each update just re-queries the
invoice list directly.
"""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .const import (
    CONF_EMPTY,
    CONF_ERR_CANNOT_CONNECT,
    CONF_ERR_INVALID_AUTH,
    CONF_ERR_UNKNOWN,
    CONF_SUCCESS,
    ID_BILL_AMOUNT,
    ID_BILL_HISTORY,
    ID_CONSUMPTION,
    ID_FROM_DATE,
    ID_LATEST_UPDATE,
    ID_METER_INDEX,
    ID_PAYMENT_STATUS,
    ID_TO_DATE,
    STATUS_PAID,
    STATUS_UNPAID,
    URL_INVOICES,
    URL_LOGIN,
)

_LOGGER = logging.getLogger(__name__)

_BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://cskh.wadaco.com.vn",
    "Referer": "https://cskh.wadaco.com.vn/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

_DOTNET_DATE_RE = re.compile(r"/Date\((-?\d+)([+-]\d{4})?\)/")


def _parse_dotnet_date(value: str | None) -> datetime | None:
    """Parse a `/Date(1783218472000+0700)/`-style timestamp."""
    if not value:
        return None
    match = _DOTNET_DATE_RE.match(value)
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000).astimezone()


def _format_date(value: str | None) -> str:
    parsed = _parse_dotnet_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


class WadacoAPI:
    """Client for the Wadaco customer-care API (myservice.citywork.vn)."""

    def __init__(self, hass: HomeAssistant, is_new_session: bool = False) -> None:
        self.hass = hass
        self._session = (
            async_create_clientsession(hass)
            if is_new_session
            else async_get_clientsession(hass)
        )

    async def login(self, org_code: str, customer_code: str, password: str) -> dict[str, Any]:
        """Validate the account credentials.

        The login endpoint expects a single `userName` combining the branch
        code the user picks up front with their customer code, as
        `<org_code>_<customer_code>` - not the bare customer code.
        """
        try:
            resp = await self._session.post(
                url=URL_LOGIN,
                json={
                    "userName": f"{org_code}_{customer_code}",
                    "password": password,
                },
                headers=_BASE_HEADERS,
            )
        except Exception as e:
            _LOGGER.error("Login connection error: %s", e)
            return {"status": CONF_ERR_CANNOT_CONNECT}

        status, resp_json = await _process_response(resp)
        if status != CONF_SUCCESS:
            return {"status": status}

        result = resp_json.get("result") or {}
        if not result.get("access_token"):
            return {"status": CONF_ERR_INVALID_AUTH}

        return {"status": CONF_SUCCESS}

    async def get_year_invoices(
        self, org_code: str, customer_code: str, year: int, limit: int = 12
    ) -> dict:
        """Fetch the current year's invoices/meter readings."""
        try:
            resp = await self._session.get(
                url=URL_INVOICES,
                params={
                    "maKhachHang": customer_code,
                    "limit": limit,
                    "orgCode": org_code,
                    "nam": year,
                },
                headers=_BASE_HEADERS,
            )
        except Exception as e:
            _LOGGER.error("Get invoices error: %s", e)
            return {"status": CONF_ERR_CANNOT_CONNECT}

        status, resp_json = await _process_response(resp)
        if status != CONF_SUCCESS:
            return {"status": status}

        invoices = resp_json.get("result") or []
        invoices.sort(key=lambda b: (b.get("nam", 0), b.get("thang", 0)), reverse=True)
        return {"status": CONF_SUCCESS, "data": invoices}

    async def request_update(self, org_code: str, customer_code: str) -> dict[str, Any]:
        """Fetch this year's invoices and build the sensor data dict."""
        invoices = await self.get_year_invoices(org_code, customer_code, datetime.now().year)
        if invoices["status"] != CONF_SUCCESS:
            return {"status": invoices["status"]}

        data = invoices["data"]
        if not data:
            return {"status": CONF_EMPTY}

        return _format_result(data)


async def _process_response(resp) -> tuple:
    if resp.status == 401:
        return CONF_ERR_INVALID_AUTH, {}

    if resp.status != 200:
        _LOGGER.error("HTTP error %s", resp.status)
        return CONF_ERR_CANNOT_CONNECT, {}

    try:
        data = await resp.json(content_type=None)
        return CONF_SUCCESS, data
    except Exception as e:
        _LOGGER.error("JSON parse error: %s", e)
        return CONF_ERR_UNKNOWN, {}


def _format_bill(bill: dict) -> dict[str, Any]:
    """Extract the fields worth exposing from one invoice/meter reading.

    Includes enough of the raw invoice (line items, rates, amount-in-words,
    invoice date) to render a full receipt, not just the total.
    """
    return {
        "period": f"{bill.get('thang', '')}/{bill.get('nam', '')}",
        "invoice_no": bill.get("soHoaDon", ""),
        "invoice_series": bill.get("seriHoaDon", ""),
        "meter_no": bill.get("seriDongHo", ""),
        "old_index": bill.get("chiSoDau", 0),
        "new_index": bill.get("chiSoCuoi", 0),
        "consumption_m3": bill.get("tieuThu", 0),
        "from_date": _format_date(bill.get("ngayDauKy")),
        "to_date": _format_date(bill.get("ngayCuoiKy")),
        "read_date": _format_date(bill.get("ngayDoc")),
        "invoice_date": _format_date(bill.get("ngayLapHoaDon")),
        "detail_items": [
            {
                "name": item.get("hangMucChiTiet", ""),
                "quantity": item.get("soLuong", 0),
                "unit_price": item.get("donGia", 0),
                "amount": item.get("thanhTien", 0),
            }
            for item in bill.get("dsChiTiet") or []
        ],
        "amount_before_fees": bill.get("thanhTien", 0),
        "vat_rate": bill.get("mucVAT", 0),
        "vat": bill.get("phiVAT", 0),
        "environment_fee_rate": bill.get("mucBVMT", 0),
        "environment_fee": bill.get("phiBVMT", 0),
        "wastewater_fee": bill.get("phiThai", 0),
        "total_amount": bill.get("tongTien", 0),
        "total_amount_words": bill.get("tongTienBangChu", ""),
        "paid": bool(bill.get("daThanhToan", False)),
    }


def _format_result(invoices: list) -> dict[str, Any]:
    """Build the sensor data dict from the (newest-first) invoice list."""
    latest = _format_bill(invoices[0])
    time_obj = datetime.now()

    return {
        "status": CONF_SUCCESS,
        ID_CONSUMPTION: {"value": latest["consumption_m3"]},
        ID_METER_INDEX: {
            "value": latest["new_index"],
            "old_index": latest["old_index"],
            "meter_no": latest["meter_no"],
        },
        ID_BILL_AMOUNT: {
            "value": latest["total_amount"],
            "info": (
                "mdi:checkbox-marked-circle-outline"
                if latest["paid"]
                else "mdi:alert-circle-outline"
            ),
            **latest,
        },
        ID_PAYMENT_STATUS: {
            "value": STATUS_PAID if latest["paid"] else STATUS_UNPAID,
            "info": (
                "mdi:comment-check-outline"
                if latest["paid"]
                else "mdi:comment-alert-outline"
            ),
        },
        ID_FROM_DATE: {"value": latest["from_date"]},
        ID_TO_DATE: {"value": latest["read_date"]},
        ID_LATEST_UPDATE: {"value": time_obj.astimezone()},
        ID_BILL_HISTORY: {"value": [_format_bill(b) for b in invoices]},
    }
