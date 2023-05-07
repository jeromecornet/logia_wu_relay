import logging
import math

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
    add_devices([LogiaFeelsLikeSensor(device_name, url, "Outdoor", sensor_info)])
    add_devices([LogiaHumixexSensor(device_name, url, "Outdoor", sensor_info)])
    add_devices([LogiaWindChillSensor(device_name, url, "Outdoor", sensor_info)])        

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

class LogiaHumixexSensor(SensorEntity):
    def __init__(self, device_name, url, base, sensor_info):
        name = device_name or "Logia"
        self._url = url
        self._attr_name = name + " " + base + " Humidex"
        self._recorded_value = None
        self._unique_id = url+"-"+base+"-humidex"
        self._sensor_info = sensor_info
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, url+base)},
            name_by_user=name + base,
            manufacturer="Logia"
        )


    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE
    
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
        return '°C'
    
    @property
    def suggested_display_precision(self):
        return 1

    @property
    def native_value(self):
        return self._recorded_value

    def update(self):
        response = requests.get(self._url)            
        data = response.json()
        tempfs = measureOrNone(data, "tempf")
        dewfs = measureOrNone(data, "dewptf")
        if tempfs is None or dewfs is None:
            self._recorded_value = None
        elif float(tempfs) < 75:
            self._recorded_value = None
        else:
            tempc = (float(tempfs) - 32.0)/1.8
            dewc = (float(dewfs) - 32.0)/1.8
            # Environment Canada Humidex formula
            self._recorded_value = round(tempc + 0.555*(6.11*math.exp(5417.7530*(1.0/273.16 - 1.0/(273.15+dewc)))-10),1)
         
class LogiaWindChillSensor(SensorEntity):
    def __init__(self, device_name, url, base, sensor_info):
        name = device_name or "Logia"
        self._url = url
        self._attr_name = name + " " + base + " Wind Chill"
        self._recorded_value = None
        self._unique_id = url+"-"+base+"-windchill"
        self._sensor_info = sensor_info
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, url+base)},
            name_by_user=name + base,
            manufacturer="Logia"
        )


    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE
    
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
        return '°C'
    
    @property
    def suggested_display_precision(self):
        return 1

    @property
    def native_value(self):
        return self._recorded_value

    def update(self):
        response = requests.get(self._url)            
        data = response.json()
        tempfs = measureOrNone(data, "tempf")
        vms = measureOrNone(data, "windgustmph")
        if tempfs is None or vms is None:
            self._recorded_value = None
        else:
            tempf = float(tempfs)
            vm = float(vms)
            if tempf > 50:
                self._recorded_value =  None
            elif vm is None or vm < 3:
                self._recorded_value =  round((tempf - 32.0)/1.8,1)
            else:
                # Environment Wind Chill formula in F
                wcf = 35.74 + 0.6215 * tempf - 35.75*math.pow(vm, 0.16) + 0.4275*tempf*math.pow(vm, 0.16)
                self._recorded_value = round((wcf - 32.0)/1.8,1)

 
class LogiaFeelsLikeSensor(SensorEntity):
    def __init__(self, device_name, url, base, sensor_info):
        name = device_name or "Logia"
        self._url = url
        self._attr_name = name + " " + base + " Feels Like"
        self._recorded_value = None
        self._unique_id = url+"-"+base+"-feelslike"
        self._sensor_info = sensor_info
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, url+base)},
            name_by_user=name + base,
            manufacturer="Logia"
        )


    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE
    
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
        return '°C'
    
    @property
    def suggested_display_precision(self):
        return 1

    @property
    def native_value(self):
        return self._recorded_value

    def update(self):
        response = requests.get(self._url)            
        data = response.json()
        vms = measureOrNone(data, "windgustmph")            
        tempfs = measureOrNone(data, "tempf")
        dewfs = measureOrNone(data, "dewptf")
        if tempfs is None or vms is None or dewfs is None:
            self._recorded_value = None
        else:
            tempf = float(tempfs)
            dewf = float(dewfs)
            vm = float(vms)
            if tempf > 75:
                tempc = (tempf - 32.0)/1.8
                dewc = (dewf - 32.0)/1.8
                # Environment Canada Humidex formula
                self._recorded_value = round(tempc + 0.555*(6.11*math.exp(5417.7530*(1.0/273.16 - 1.0/(273.15+dewc)))-10),1)
            elif tempf < 50 and vm > 3:                
                # Environment Wind Chill formula in F
                wc = 35.74 + 0.6215 * tempf - 35.75*math.pow(vm, 0.16) + 0.4275*tempf*math.pow(vm, 0.16)
                self._recorded_value = round((wc - 32.0)/1.8,1)
            else:
                self._recorded_value = round((tempf - 32.0)/1.8,1)
                                                

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
    def suggested_display_precision(self):
        return 1
    
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

                                    