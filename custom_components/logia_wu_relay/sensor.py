"""Sensor platform for the Logia Weather Underground relay.

The weather station posts its readings to ``rtupdate.wunderground.com``, which is
redirected (DNS) to a small web server that dumps the decoded query string into a
JSON file.  This platform mirrors that file into Home Assistant sensors.
"""

from __future__ import annotations

import logging
import math
import threading
import time

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.helpers import config_validation as cv

try:  # Home Assistant >= 2023.8
    from homeassistant.helpers.device_registry import DeviceInfo
except ImportError:  # pragma: no cover - older Home Assistant
    from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_URL = "url"

#: Readings older than this are reported as unknown instead of stale values.
STALE_TIMEOUT_MINUTES = 15

#: Timeout for the HTTP request to the relay.
HTTP_TIMEOUT = 10

#: All entities poll on their own schedule; share a single request per cycle.
CACHE_TTL = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

LOGIA_BASE_SENSORS = [
    {
        "attr_name": "Temperature",
        "attr_key": "indoortempf",
        "sensor_type": SensorDeviceClass.TEMPERATURE,
        "unit": "°F",
    },
    {
        "attr_name": "Relative Humidity",
        "attr_key": "indoorhumidity",
        "sensor_type": SensorDeviceClass.HUMIDITY,
        "unit": "%",
    },
]

LOGIA_51_SENSORS = [
    {
        "attr_name": "Atmospheric pressure",
        "attr_key": "baromin",
        "sensor_type": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "unit": "inHg",
    },
    {
        "attr_name": "Temperature",
        "attr_key": "tempf",
        "sensor_type": SensorDeviceClass.TEMPERATURE,
        "unit": "°F",
    },
    {
        "attr_name": "Dew Point",
        "attr_key": "dewptf",
        "sensor_type": SensorDeviceClass.TEMPERATURE,
        "unit": "°F",
    },
    {
        "attr_name": "Relative Humidity",
        "attr_key": "humidity",
        "sensor_type": SensorDeviceClass.HUMIDITY,
        "unit": "%",
    },
    {
        "attr_name": "Wind Speed",
        "attr_key": "windspeedmph",
        "sensor_type": SensorDeviceClass.WIND_SPEED,
        "unit": "mph",
    },
    {
        "attr_name": "Wind Gust",
        "attr_key": "windgustmph",
        "sensor_type": SensorDeviceClass.WIND_SPEED,
        "unit": "mph",
    },
    # SensorDeviceClass.WIND_DIRECTION expects degrees and would make Home
    # Assistant drop the non-numeric unit, so direction is handled separately
    # by LogiaWindSensor.
    {
        "attr_name": "Hourly Rain",
        "attr_key": "rainin",
        "sensor_type": SensorDeviceClass.PRECIPITATION,
        "unit": "in",
    },
    {
        "attr_name": "Daily Rain",
        "attr_key": "dailyrainin",
        "sensor_type": SensorDeviceClass.PRECIPITATION,
        "unit": "in",
    },
]

# --- shared fetching -------------------------------------------------------

_cache_lock = threading.Lock()
_cache: dict[str, object] = {"url": None, "payload": None, "fetched": 0.0}


def fetch_payload(url: str) -> dict | None:
    """Return the decoded payload, re-using a recent fetch when possible.

    The platform creates ~14 entities and each one polls independently; without
    this cache every poll cycle would issue 14 identical HTTP requests.
    """
    now = time.monotonic()
    with _cache_lock:
        if _cache["url"] == url and now - _cache["fetched"] < CACHE_TTL:
            return _cache["payload"]

    payload = None
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as err:
        # A partial read is possible: the relay truncates the file before
        # writing the new payload.
        _LOGGER.debug("Cannot read relay payload from %s: %s", url, err)

    with _cache_lock:
        _cache["url"] = url
        _cache["payload"] = payload
        _cache["fetched"] = time.monotonic()

    if not isinstance(payload, dict):
        return None
    return payload


def reading(payload: dict | None, key: str) -> float | None:
    """Return a numeric reading, or None when missing/failed/stale."""
    if not isinstance(payload, dict):
        return None

    timestamp = payload.get("dateutc")
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        return None
    if time.time() - timestamp >= STALE_TIMEOUT_MINUTES * 60:
        return None

    try:
        return float(payload[key])
    except (KeyError, TypeError, ValueError):
        return None


# --- entities --------------------------------------------------------------


class LogiaSensorBase(SensorEntity):
    """Common plumbing for the entities built from the relay payload."""

    def __init__(self, device_name: str, url: str, base: str, key: str) -> None:
        self._url = url
        self._key = key
        self._value: float | None = None
        self._attr_unique_id = f"{DOMAIN}{url}-{base}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{url}{base}")},
            name=f"{device_name} {base}",
            manufacturer="Logia",
            model="Weather station (WU relay)",
        )

    @property
    def native_value(self) -> float | None:
        """Return the last computed value."""
        return self._value

    def update(self) -> None:
        """Poll the relay."""
        self._value = self.compute(fetch_payload(self._url))

    def compute(self, payload: dict | None) -> float | None:
        """Turn a payload into this entity's value."""
        return reading(payload, self._key)


class LogiaRelaySensor(LogiaSensorBase):
    """Plain passthrough sensor, one per published field."""

    def __init__(self, device_name, url, base, sensor_info) -> None:
        super().__init__(device_name, url, base, sensor_info["attr_key"])
        self._attr_name = f"{device_name} {base} {sensor_info['attr_name']}"
        self._attr_device_class = sensor_info["sensor_type"]
        self._attr_native_unit_of_measurement = sensor_info["unit"]


class LogiaWindSensor(LogiaSensorBase):
    """Wind direction in degrees."""

    def __init__(self, device_name, url, base) -> None:
        super().__init__(device_name, url, base, "winddir")
        self._attr_name = f"{device_name} {base} Wind Direction"
        self._attr_native_unit_of_measurement = "˚"
        self._attr_icon = "mdi:weather-windy"


class LogiaHumidexSensor(LogiaSensorBase):
    """Environment Canada humidex (only meaningful above 75°F)."""

    def __init__(self, device_name, url, base) -> None:
        super().__init__(device_name, url, base, "humidex")
        self._attr_name = f"{device_name} {base} Humidex"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = 1

    def compute(self, payload):
        tempf = reading(payload, "tempf")
        dewptf = reading(payload, "dewptf")
        if tempf is None or dewptf is None or tempf < 75:
            return None
        return round(_humidex(_to_celsius(tempf), _to_celsius(dewptf)), 1)


class LogiaWindChillSensor(LogiaSensorBase):
    """Environment Canada wind chill (only meaningful below 50°F)."""

    def __init__(self, device_name, url, base) -> None:
        super().__init__(device_name, url, base, "windchill")
        self._attr_name = f"{device_name} {base} Wind Chill"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = 1

    def compute(self, payload):
        tempf = reading(payload, "tempf")
        windmph = reading(payload, "windgustmph")
        if tempf is None or windmph is None or tempf > 50:
            return None
        if windmph < 3:
            return round(_to_celsius(tempf), 1)
        return round(_to_celsius(_wind_chill(tempf, windmph)), 1)


class LogiaFeelsLikeSensor(LogiaSensorBase):
    """Stick to humidex in the heat, wind chill in the cold."""

    def __init__(self, device_name, url, base) -> None:
        super().__init__(device_name, url, base, "feelslike")
        self._attr_name = f"{device_name} {base} Feels Like"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = 1

    def compute(self, payload):
        tempf = reading(payload, "tempf")
        windmph = reading(payload, "windgustmph")
        dewptf = reading(payload, "dewptf")
        if tempf is None or windmph is None or dewptf is None:
            return None
        if tempf > 75:
            return round(_humidex(_to_celsius(tempf), _to_celsius(dewptf)), 1)
        if tempf < 50 and windmph > 3:
            return round(_to_celsius(_wind_chill(tempf, windmph)), 1)
        return round(_to_celsius(tempf), 1)


# --- helpers ---------------------------------------------------------------


def _to_celsius(tempf: float) -> float:
    return (tempf - 32.0) / 1.8


def _humidex(tempc: float, dewc: float) -> float:
    """Environment Canada humidex."""
    dew_point_kelvin = 273.15 + dewc
    vapour_pressure = 6.11 * math.exp(5417.7530 * (1.0 / 273.16 - 1.0 / dew_point_kelvin))
    return tempc + 0.555 * (vapour_pressure - 10)


def _wind_chill(tempf: float, windmph: float) -> float:
    """Environment Canada wind chill, in °F."""
    wind_factor = math.pow(windmph, 0.16)
    return 35.74 + 0.6215 * tempf - 35.75 * wind_factor + 0.4275 * tempf * wind_factor


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Logia relay sensors."""
    device_name = config.get(CONF_NAME) or "Logia"
    url = config[CONF_URL]

    entities = [
        LogiaRelaySensor(device_name, url, "Outdoor", sensor_info)
        for sensor_info in LOGIA_51_SENSORS
    ]
    entities.extend(
        LogiaRelaySensor(device_name, url, "Indoor", sensor_info)
        for sensor_info in LOGIA_BASE_SENSORS
    )
    entities.extend(
        [
            LogiaWindSensor(device_name, url, "Outdoor"),
            LogiaFeelsLikeSensor(device_name, url, "Outdoor"),
            LogiaHumidexSensor(device_name, url, "Outdoor"),
            LogiaWindChillSensor(device_name, url, "Outdoor"),
        ]
    )

    add_entities(entities)
