# ThermoBeacon exporter

Prometheus exporter for ThermoBeacon sensors.
Requires Python and BlueZ.

The scan type is passive which is a BlueZ experimental feature so you need to set `Experimental = true` in `/etc/bluetooth/main.conf`.
Exported metrics:

- sensor_temperature_celsius{address} (gauge)
- sensor_humidity_percent{address} (gauge)
- sensor_voltage{address} (gauge)
- sensor_uptime_seconds{address} (gauge)
- sensor_location_info{address, location} (constant gauge, metadata)

Locations for the metadata gauge are in `resources/locations.csv`.

## Data sources

BLE advertising packets are processed passively. There are 2 packet types, 18B and 20B. The 18B contains temperature and humidity encoded like this (little endian):

```
00 00 <6B MAC> <u16 voltage [mV]> <i16 temp [°C/16]> <u16 humidity [%/16]> <u32 uptime [s]>
```
