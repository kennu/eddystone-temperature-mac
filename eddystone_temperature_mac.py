"""
Read temperature information from Eddystone beacons.

Your beacons must be configured to transmit UID (for identification) and TLM
(for temperature) frames, or you can use the MAC address of the beacon.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.eddystone_temperature/

This version was forked from the built-in Home Assistant eddystone_temperature
module by Kenneth Falck <kennu@iki.fi> in 2018. You can configure it like this:

sensor:
  - platform: eddystone_temperature_mac
    beacons:
      home_freezer:
        name: "Home Freezer"
        mac: "01:23:45:67:89:ab"

This version also includes a fix to convert the Eddystone TLM temperature from
8.8 fixed point format to Python floats.

"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, TEMP_CELSIUS, STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP,
    EVENT_HOMEASSISTANT_START)
import struct

REQUIREMENTS = ['beacontools[scan]==1.2.3', 'construct==2.9.41']

_LOGGER = logging.getLogger(__name__)

CONF_BEACONS = 'beacons'
CONF_BT_DEVICE_ID = 'bt_device_id'
CONF_INSTANCE = 'instance'
CONF_NAMESPACE = 'namespace'
CONF_MAC = 'mac'

BEACON_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAMESPACE): cv.string,
    vol.Optional(CONF_INSTANCE): cv.string,
    vol.Optional(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BT_DEVICE_ID, default=0): cv.positive_int,
    vol.Required(CONF_BEACONS): vol.Schema({cv.string: BEACON_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Validate configuration, create devices and start monitoring thread."""
    bt_device_id = config.get("bt_device_id")

    beacons = config.get("beacons")
    devices = []

    for dev_name, properties in beacons.items():
        namespace = get_from_conf(properties, "namespace", 20)
        instance = get_from_conf(properties, "instance", 12)
        mac = get_from_conf(properties, "mac", 17)
        name = properties.get(CONF_NAME, dev_name)

        if (instance is None or namespace is None) and (mac is None):
            _LOGGER.error("Skipping %s", dev_name)
            continue
        else:
            devices.append(EddystoneTemp(name, namespace, instance, mac))

    if devices:
        mon = Monitor(hass, devices, bt_device_id)

        def monitor_stop(_service_or_event):
            """Stop the monitor thread."""
            _LOGGER.info("Stopping scanner for Eddystone beacons")
            mon.stop()

        def monitor_start(_service_or_event):
            """Start the monitor thread."""
            _LOGGER.info("Starting scanner for Eddystone beacons")
            mon.start()

        add_devices(devices)
        mon.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, monitor_stop)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, monitor_start)
    else:
        _LOGGER.warning("No devices were added")


def get_from_conf(config, config_key, length):
    """Retrieve value from config and validate length."""
    string = config.get(config_key)
    if string and len(string) != length:
        _LOGGER.error("Error in config parameter %s: Must be exactly %d "
                      "bytes. Device will not be added", config_key, length/2)
        return None
    return string


class EddystoneTemp(Entity):
    """Representation of a temperature sensor."""

    def __init__(self, name, namespace, instance, mac):
        """Initialize a sensor."""
        self._name = name
        self.namespace = namespace
        self.instance = instance
        self.mac = mac
        self.bt_addr = None
        self.temperature = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS

    @property
    def should_poll(self):
        """Return the polling state."""
        return False


class Monitor:
    """Continuously scan for BLE advertisements."""

    def __init__(self, hass, devices, bt_device_id):
        """Construct interface object."""
        self.hass = hass

        # List of beacons to monitor
        self.devices = devices
        # Number of the bt device (hciX)
        self.bt_device_id = bt_device_id

        def callback(bt_addr, _, packet, additional_info):
            """Handle new packets."""
            temperature = struct.unpack('<h', struct.pack('>H', packet.temperature))[0] / 256
            self.process_packet(
                additional_info['namespace'] if additional_info else None, additional_info['instance'] if additional_info else None, bt_addr,
                temperature)

        # pylint: disable=import-error
        from beacontools import (
            BeaconScanner, BtAddrFilter, EddystoneFilter, EddystoneTLMFrame)
        device_filters = [(BtAddrFilter(d.mac) if d.mac else EddystoneFilter(d.namespace, d.instance))
                          for d in devices]

        self.scanner = BeaconScanner(
            callback, bt_device_id, device_filters, EddystoneTLMFrame)
        self.scanning = False

    def start(self):
        """Continuously scan for BLE advertisements."""
        if not self.scanning:
            self.scanner.start()
            self.scanning = True
        else:
            _LOGGER.debug(
                "start() called, but scanner is already running")

    def process_packet(self, namespace, instance, mac, temperature):
        """Assign temperature to device."""
        _LOGGER.debug("Received temperature for <%s,%s,%s>: %d",
                      namespace, instance, mac, temperature)

        for dev in self.devices:
            if (dev.namespace and dev.instance and dev.namespace == namespace and dev.instance == instance) or (dev.mac and dev.mac == mac):
                if dev.temperature != temperature:
                    dev.temperature = temperature
                    dev.schedule_update_ha_state()

    def stop(self):
        """Signal runner to stop and join thread."""
        if self.scanning:
            _LOGGER.debug("Stopping...")
            self.scanner.stop()
            _LOGGER.debug("Stopped")
            self.scanning = False
        else:
            _LOGGER.debug(
                "stop() called but scanner was not running")
