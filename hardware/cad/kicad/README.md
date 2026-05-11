# KiCad CAD Package (No Raspberry Pi)

This directory provides a KiCad project for your graduation hardware section:

- `smart_home_esp32.kicad_pro`
- `smart_home_esp32.kicad_sch`
- `smart_home_esp32.kicad_pcb`
- `BOM.csv`

## Tool Version

- Recommended: KiCad 7 or 8

## Functional Blocks

1. ESP32 core control board
2. Sensor interfaces:
   - DHT22 (temperature/humidity)
   - MQ-2 (gas)
3. Actuator interfaces:
   - Relay CH1 (light)
   - Relay CH2 (fan)
4. Manual button + status LED
5. UART debug/program header

## Net Connection Plan

- `3V3` -> ESP32, DHT22
- `5V` -> relay module, MQ-2 module
- `GND` -> all modules common ground
- `GPIO4` -> DHT22 DATA
- `GPIO34` -> MQ-2 AO
- `GPIO26` -> Relay CH1 IN
- `GPIO27` -> Relay CH2 IN
- `GPIO18` -> Button input
- `GPIO2` -> Status LED
- `UART_TX/UART_RX` -> debug header

## PCB Layout Recommendations

1. Place ESP32 at board center-left for better antenna clearance.
2. Keep MQ-2 analog line short and away from relay switching traces.
3. Use at least 0.8 mm trace width for 5V and GND trunk.
4. Keep relay/load connectors at board right edge.
5. Add GND copper pours on both sides.

## DRC / ERC

- Track width >= 0.25 mm (signal), >= 0.8 mm (power)
- Clearance >= 0.2 mm
- Board thickness: 1.6 mm

## For Thesis Figures

You can export:

- Schematic PDF from Eeschema
- 2D PCB screenshot (front/back)
- 3D PCB rendering from PCB Editor
- BOM from `BOM.csv`

