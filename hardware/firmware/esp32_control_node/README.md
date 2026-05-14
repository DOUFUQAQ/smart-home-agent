# ESP32 #2 Executor/Broadcast Node Firmware

This firmware is for **ESP32 Node #2 (executor + broadcast)**:

- Relay control for light/socket/fan
- MAX98357 I2S audio amplifier output
- WiFi polling for backend control commands

## Pin Map (Node #2)

- Relay light IN -> `GPIO16`
- Relay socket IN -> `GPIO17`
- Relay fan IN -> `GPIO18`
- MAX98357 BCLK -> `GPIO26`
- MAX98357 LRC/LRCLK -> `GPIO25`
- MAX98357 DIN -> `GPIO22`
- MAX98357 SD/EN -> `GPIO21`
- MAX98357 GAIN -> default floating (or strap for fixed gain)
- Status LED (optional) -> `GPIO2`

## Backend Endpoints Used

- `GET /api/devices` (poll to fetch target state)
- `PATCH /api/devices/{device_id}/state` (push runtime state)

## Flash Steps

1. Open `esp32_control_node.ino` in Arduino IDE.
2. Select board `ESP32 Dev Module`.
3. Update:
   - `WIFI_SSID`
   - `WIFI_PASS`
   - `API_BASE`
   - `DEVICE_ID` (executor node device id)
4. Upload and open Serial Monitor (`115200`).

## Notes

1. MAX98357 pins are prepared as I2S output interface.
2. `GAIN` pin is hardware strap (not controlled by firmware in current design).
3. Typical `GAIN` options: floating 9 dB, GND 12 dB, 100k-to-GND 15 dB, 3V3 6 dB, 100k-to-3V3 3 dB.
4. Relay outputs assume low-level trigger modules.
5. See `../../PIN_CONNECTION_GUIDE.md` for full wiring.
