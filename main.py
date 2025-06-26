import asyncio
import argparse
import logging
import csv
import os
from bleak import BleakScanner
from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
from bleak.backends.bluezdbus.scanner import BlueZScannerArgs, BlueZDiscoveryFilters
from bleak.assigned_numbers import AdvertisementDataType
from prometheus_client import Gauge, start_http_server

# === CONFIG ===
TARGET_NAME = "ThermoBeacon"
SERVICE_UUID = b"\xf0\xff"  # little-endian 0xFFF0
MANUFACTURER_ID = 0x0010

# === Logging ===
logging.basicConfig(level=logging.INFO)

# === Prometheus metric with address label ===
temperature_gauge = Gauge(
    "sensor_temperature_celsius", "Temperature from BLE sensor", ["address"]
)

humidity_gauge = Gauge(
    "sensor_humidity_percent", "Humidity from BLE sensor", ["address"]
)

location_gauge = Gauge(
    "sensor_location_info",
    "ThermoBeacon location metadata",
    ["address", "location"],
)


# === Decoder ===
def decode_packet(data: bytes):
    """
    Decode raw bytes to temperature (°C) and humidity (%RH)
    """

    temperature_raw = int.from_bytes(data[10:12], "little")
    humidity_raw = int.from_bytes(data[12:14], "little")

    temperature = temperature_raw / 16.0
    humidity = humidity_raw / 16.0

    return temperature, humidity


# === Scanner callback ===
def detection_callback(device, advertisement_data):
    device_name = advertisement_data.local_name or device.name or ""
    if device_name != TARGET_NAME:
        return

    mfg_data = advertisement_data.manufacturer_data.get(MANUFACTURER_ID)
    if mfg_data:
        if len(mfg_data) == 20:
            logging.info(
                "ADV (%dB) [%s]: %s",
                len(mfg_data),
                device.address,
                mfg_data.hex(),
            )
            return
        temperature, humidity = decode_packet(mfg_data)
        if temperature is not None and humidity is not None:
            logging.info(
                "ADV (%dB) [%s]: %s -> %.1f°C, %.1f%% RH",
                len(mfg_data),
                device.address,
                mfg_data.hex(),
                temperature,
                humidity,
            )
            temperature_gauge.labels(address=device.address).set(temperature)
            humidity_gauge.labels(address=device.address).set(humidity)


def set_location_gauge():
    """
    Load location metadata from CSV file and set the location info gauge."""
    script_dir = os.path.dirname(os.path.realpath(__file__))
    with open(f"{script_dir}/resources/locations.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) == 2:
                address, location = row
                location_gauge.labels(
                    address=address.strip(), location=location.strip()
                ).set(1)
        logging.info("Loaded location metadata from CSV")


# === Main scan loop ===
async def run_scan():
    scanner = BleakScanner(
        detection_callback,
        scanning_mode="passive",
        bluez=BlueZScannerArgs(
            filters=BlueZDiscoveryFilters(Pattern=TARGET_NAME),
            or_patterns=[
                OrPattern(
                    0,
                    AdvertisementDataType.INCOMPLETE_LIST_SERVICE_UUID16,
                    SERVICE_UUID,
                ),
            ],
        ),
    )

    await scanner.start()
    logging.info("Scanner started.")
    while True:
        await asyncio.sleep(1)


# === Entry point ===
async def main():
    parser = argparse.ArgumentParser(
        description="BLE Advertisement to Prometheus Exporter (Name-filtered, multi-device)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Prometheus metrics port"
    )
    args = parser.parse_args()

    set_location_gauge()

    # Start Prometheus server
    start_http_server(args.port)
    logging.info("Prometheus metrics server started on port %d", args.port)

    # Start BLE scanner
    await run_scan()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Exiting.")
