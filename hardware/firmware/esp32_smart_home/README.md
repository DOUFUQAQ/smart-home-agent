# ESP32 #1 Collector Node Firmware

This firmware is for **ESP32 Node #1 (collector)**:

- INMP441 voice capture input (I2S RX pins)
- DHT22 temperature/humidity sampling
- MQ-2 gas analog sampling
- WiFi uplink to backend

## Pin Map (Node #1)

- DHT22 DATA -> `GPIO4`
- MQ-2 AO -> `GPIO34` (ADC1, must use voltage divider)
- INMP441 BCLK -> `GPIO26`
- INMP441 WS/LRCLK -> `GPIO27`
- INMP441 SD -> `GPIO33`
- Status LED (optional) -> `GPIO2`

## Backend Endpoints Used

- `PATCH /api/devices/{device_id}/state`
- `POST /api/readings`

## Flash Steps

1. Open `esp32_smart_home.ino` in Arduino IDE.
2. Select board `ESP32 Dev Module`.
3. Update:
   - `WIFI_SSID`
   - `WIFI_PASS`
   - `API_BASE`
   - `DEVICE_ID` (collector node device id)
4. Upload and open Serial Monitor (`115200`).

## Notes

1. Current firmware keeps INMP441 pin constants ready and sensor uplink stable.
2. Voice stream upload pipeline can be implemented on top of these I2S pins.
3. See `../../PIN_CONNECTION_GUIDE.md` for full two-node wiring.
