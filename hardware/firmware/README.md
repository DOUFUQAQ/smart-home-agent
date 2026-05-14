# Firmware Layout

This directory now contains **two ESP32 firmware sets**:

1. `esp32_smart_home/`  
   Node #1 collector firmware (INMP441 + DHT22 + MQ-2, uplink).
2. `esp32_control_node/`  
   Node #2 executor firmware (relay control + MAX98357 playback).

Both nodes connect to the same backend over WiFi.
