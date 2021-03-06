# Home Assistant Eddystone Temperature (MAC filtering support)

Read temperature information from Eddystone beacons.

Your beacons must be configured to transmit UID (for identification) and TLM
(for temperature) frames, or you can use the MAC address of the beacon.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.eddystone_temperature/

This version was forked from the built-in Home Assistant eddystone_temperature
module by Kenneth Falck <kennu@iki.fi> in 2018.

This version also includes a fix to convert the Eddystone TLM temperature from
8.8 fixed point format to Python floats.

This has been tested with RuuviTag with the Eddystone firmware installed.

## Installation

Install by running these commands (on Linux):

    mkdir -p ~/.homeassistant/custom_components/sensor/
    cp eddystone_temperature_mac.py ~/.homeassistant/custom_components/sensor/

## Configuration

Configure by adding this section in ~/.homeassistant/configuration.yaml:

    sensor:
      - platform: eddystone_temperature_mac
        beacons:
          home_freezer:
            name: "Home Freezer"
            mac: "01:23:45:67:89:ab"

