import logging

import voluptuous as vol

from homeassistant.components.sensor import  PLATFORM_SCHEMA, SensorEntity, SensorDeviceClass
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from . import DOMAIN
from datetime import datetime

REQUIREMENTS = [ "requests" ]
import requests

_LOGGER = logging.getLogger(__name__)

CONF_URL = "url"
STALE_TIMEOUT_MINUTES = 15

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})


LOGIA_BASE_SENSORS =  [{ 
        "attr_name": 'Temperature',
        "attr_key": 'indoortempf',
        "sensor_type": SensorDeviceClass.TEMPERATURE,
        "unit": '°F',
    },
  
      { 
        "attr_name": 'Relative Humidity',
        "attr_key": 'indoorhumidity',
        "sensor_type": SensorDeviceClass.HUMIDITY,
        "unit": '%',
    }]

LOGIA_51_SENSORS = [
   
    { 
        "attr_name": 'Atmospheric pressure',
        "attr_key": 'baromin',
        "sensor_type": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "unit": 'inHg',
    },
     { 
        "attr_name": 'Temperature',
        "attr_key": 'tempf',
        "sensor_type": SensorDeviceClass.TEMPERATURE,
        "unit": '°F',
    },
     { 
        "attr_name": 'Dew Point',
        "attr_key": 'dewptf',
        "sensor_type": SensorDeviceClass.TEMPERATURE,
        "unit": '°F',
    },
      { 
        "attr_name": 'Relative Humidity',
        "attr_key": 'humidity',
        "sensor_type": SensorDeviceClass.HUMIDITY,
        "unit": '%',
    },
      { 
        "attr_name": 'Wind Speed',
        "attr_key": 'windspeedmph',
        "sensor_type": SensorDeviceClass.WIND_SPEED,
        "unit": 'mph',
    },
    { 
        "attr_name": 'Wind Gust',
        "attr_key": 'windgustmph',
        "sensor_type": SensorDeviceClass.WIND_SPEED,
        "unit": 'mph',
    },
    #  { 
    #     "attr_name": 'Wind Direction',
    #     "attr_key": 'winddir',
    #     "sensor_type": SensorDeviceClass.WIND_DIRECTION,
    #     "unit": '˚',
    # },
     { 
        "attr_name": 'Rain rate',
        "attr_key": 'rainin',
        "sensor_type": SensorDeviceClass.PRECIPITATION_INTENSITY,
        "unit": 'in/h',
    },
    { 
        "attr_name": 'Daily Rain',
        "attr_key": 'dailyrainin',
        "sensor_type": SensorDeviceClass.PRECIPITATION,
        "unit": 'in',
    },
    ]

def measureOrNone(data, key):
    if datetime.timestamp(datetime.now()) - data['dateutc'] < STALE_TIMEOUT_MINUTES * 60:
        return data[key]
    else:
        return None


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the lacrosse alerts mobile platform."""
    device_name = config.get(CONF_NAME)
    url = config.get(CONF_URL)
    
    for sensor_info in LOGIA_51_SENSORS:
        add_devices([LogiaRelaySensor(device_name, url, "Outdoor", sensor_info)])

    for sensor_info in LOGIA_BASE_SENSORS:
        add_devices([LogiaRelaySensor(device_name, url, "Indoor", sensor_info)])

    add_devices([LogiaWindSensor(device_name, url, "Outdoor", sensor_info)])

class LogiaWindSensor(SensorEntity):
    def __init__(self, device_name, url, base, sensor_info):
        name = device_name or "Logia"
        self._url = url
        self._attr_name = name + " " + base + " Wind Direction"
        self._recorded_value = None
        self._unique_id = url+"-"+base+"-winddir"
        self._sensor_info = sensor_info
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, url+base)},
            name_by_user=name + base,
            manufacturer="Logia"
        )


    @property
    def device_class(self):
        return None
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return  self._device_info

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name
    
    @property
    def unique_id(self):
        return DOMAIN + self._unique_id

    @property
    def native_unit_of_measurement(self):
        return '˚'
    
    @property
    def native_value(self):
        return self._recorded_value

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:weather-windy'

    def update(self):
        try:
            response = requests.get(self._url)            
            data = response.json()
            self._recorded_value = measureOrNone(data, "winddir")
        except:
            self._recorded_value = None

                                    

class LogiaRelaySensor(SensorEntity):
    def __init__(self, device_name, url, base, sensor_info):
        name = device_name or "Logia"
        self._url = url
        self._attr_name = name + " " + base + " " + sensor_info['attr_name']
        self._recorded_value = None
        self._unique_id = url+"-"+base+"-"+sensor_info['attr_key']
        self._sensor_info = sensor_info
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, url+base)},
            name_by_user=name + base,
            manufacturer="Logia"
        )

    @property
    def device_class(self):
        return self._sensor_info['sensor_type']

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return  self._device_info

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name
    
    @property
    def unique_id(self):
        return DOMAIN + self._unique_id

    @property
    def native_unit_of_measurement(self):
        return self._sensor_info['unit']
    
    @property
    def native_value(self):
        return self._recorded_value

    def update(self):
        try:
            response = requests.get(self._url)            
            data = response.json()
            self._recorded_value = measureOrNone(data, self._sensor_info['attr_key'])
        except:
            self._recorded_value = None

                                    