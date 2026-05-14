# 智能家居双 ESP32 硬件针脚连接文档

本文档对应当前最新方案：

1. 1号 ESP32：主控采集端（语音采集 + 环境采集 + 上行）
2. 2号 ESP32：执行与播报端（设备控制 + 语音播报）

---

## 1. 系统模块与职责

| 模块 | 职责 |
| --- | --- |
| 1号 ESP32 开发板主控采集模块 | 统一采集调度，对接 INMP441、DHT22、MQ-2，并通过 WiFi 上传到后端 |
| 语音采集模块（INMP441） | 拾取用户语音指令，数据送入 1号 ESP32 |
| 环境传感器采集模块（DHT22 + MQ-2） | 采集温湿度与可燃气体浓度，由 1号 ESP32 定时上报 |
| 无线 WiFi 传输模块 | 两块 ESP32 均使用板载 WiFi；1号上行数据，后端下行控制到2号 |
| 2号 ESP32 设备控制与播报模块 | 执行灯光/插座/风扇控制，并驱动音频播报 |
| 音频播放播报模块（MAX98357 + 扬声器） | 接收 2号 ESP32 的 I2S 音频数据并播报反馈/告警 |

---

## 2. 1号 ESP32（采集端）完整针脚连接

### 2.1 总表

| 功能 | 模块引脚 | 1号 ESP32 引脚 | 说明 |
| --- | --- | --- | --- |
| DHT22 数据 | DATA | GPIO4 | 建议加 10k 上拉到 3V3 |
| DHT22 电源 | VCC | 3V3 | DHT22 用 3.3V 供电 |
| DHT22 地 | GND | GND | 共地 |
| MQ-2 模拟输出 | AO | GPIO34 (ADC1) | 必须分压后接入，禁止直接上 5V |
| MQ-2 电源 | VCC | 5V/VIN | MQ-2 模块常规 5V 供电 |
| MQ-2 地 | GND | GND | 共地 |
| INMP441 位时钟 | SCK/BCLK | GPIO26 | I2S BCLK |
| INMP441 左右时钟 | WS/LRCL | GPIO27 | I2S LRCLK/WS |
| INMP441 串行数据 | SD/DOUT | GPIO33 | I2S 数据输入到 ESP32 |
| INMP441 声道选择 | L/R | GND | 设为左声道（单麦方案） |
| INMP441 电源 | VDD | 3V3 | 仅 3.3V 供电 |
| INMP441 地 | GND | GND | 共地 |
| 状态灯（可选） | LED 正极串联电阻后 | GPIO2 | 调试指示，非必须 |

### 2.2 MQ-2 分压保护

```text
MQ-2 AO ---- R1 10k ----+---- ESP32 GPIO34
                         |
                       R2 20k
                         |
                        GND
```

当 `AO = 5V` 时，GPIO34 约为 3.3V，保护 ADC 引脚。

---

## 3. 2号 ESP32（执行与播报端）完整针脚连接

### 3.1 总表

| 功能 | 模块引脚 | 2号 ESP32 引脚 | 说明 |
| --- | --- | --- | --- |
| 灯光继电器控制 | IN1 | GPIO16 | 低电平触发常见 |
| 插座继电器控制 | IN2 | GPIO17 | 低电平触发常见 |
| 风扇继电器控制 | IN3 | GPIO18 | 低电平触发常见 |
| 继电器电源 | VCC | 5V/VIN | 继电器模块 5V 供电 |
| 继电器地 | GND | GND | 共地 |
| MAX98357 I2S 位时钟 | BCLK | GPIO26 | I2S BCLK |
| MAX98357 I2S 左右时钟 | LRC/LRCLK | GPIO25 | I2S LRCLK |
| MAX98357 I2S 数据 | DIN | GPIO22 | I2S 数据输出 |
| MAX98357 使能 | SD/EN | GPIO21 | 高电平使能（可做静音控制） |
| MAX98357 增益选择 | GAIN | 默认悬空 | 悬空为默认增益；可按下表配置固定增益 |
| MAX98357 电源 | VIN | 5V/VIN | 推荐 5V 供电 |
| MAX98357 地 | GND | GND | 共地 |
| 状态灯（可选） | LED 正极串联电阻后 | GPIO2 | 调试指示，非必须 |

### 3.2 扬声器连接

| MAX98357 端子 | 连接 |
| --- | --- |
| SPK+ | 扬声器正极 |
| SPK- | 扬声器负极 |

### 3.3 MAX98357 `GAIN` 引脚配置建议

常见模块可通过 `GAIN` 脚固定模拟增益。若你们当前以语音播报为主，建议先用默认增益调试，再按噪声/音量需求调整。

| GAIN 连接方式 | 典型增益 |
| --- | --- |
| 悬空 | 9 dB（默认） |
| 直接接 GND | 12 dB |
| 通过 100k 接 GND | 15 dB |
| 直接接 3V3 | 6 dB |
| 通过 100k 接 3V3 | 3 dB |

建议：
1. 若底噪明显，优先尝试 `3V3`（6 dB）或 `3V3` 经 `100k`（3 dB）。
2. 若播报音量不足，再尝试默认 9 dB 或接地增益方案。

---

## 4. 两块 ESP32 与后端通信关系

1. 两块 ESP32 均连接同一 WiFi。
2. 1号 ESP32 上传语音数据、温湿度、气体数据到后端。
3. 后端下发设备控制与播报任务给 2号 ESP32。
4. 2号 ESP32 执行继电器动作并进行语音播报。

说明：两块 ESP32 之间不需要直连控制线，按网络协同。

---

## 5. 电源与布线要求

1. 1号与2号 ESP32 可分别 USB 供电，或共用 5V 电源。
2. 若 2号带继电器和功放，建议单独稳压 5V 电源，避免瞬态压降导致重启。
3. 所有低压模块必须共地（ESP32、传感器、继电器控制侧、功放）。
4. 市电负载侧（如交流灯、交流插座）与低压控制侧必须电气隔离，严格按安全规范接线。

---

## 6. 固件针脚常量（与当前仓库固件一致）

### 6.1 1号采集端（`hardware/firmware/esp32_smart_home`）

```cpp
constexpr int DHT_PIN = 4;
constexpr int MQ2_PIN = 34;
constexpr int INMP441_BCLK_PIN = 26;
constexpr int INMP441_WS_PIN = 27;
constexpr int INMP441_SD_PIN = 33;
constexpr int STATUS_LED_PIN = 2; // optional
```

### 6.2 2号执行端（`hardware/firmware/esp32_control_node`）

```cpp
constexpr int RELAY_LIGHT_PIN = 16;
constexpr int RELAY_SOCKET_PIN = 17;
constexpr int RELAY_FAN_PIN = 18;
constexpr int I2S_BCLK_PIN = 26;
constexpr int I2S_LRCLK_PIN = 25;
constexpr int I2S_DIN_PIN = 22;
constexpr int AMP_SD_PIN = 21;
constexpr int STATUS_LED_PIN = 2; // optional
```

---

## 7. 上电调试顺序

1. 先上电 1号 ESP32，检查 DHT22、MQ-2、INMP441 初始化与上报日志。
2. 再上电 2号 ESP32，检查继电器空载动作与 MAX98357 使能状态。
3. 后端启动后，验证 1号数据上行、2号指令下行。
4. 最后接入真实负载（灯光/插座/风扇）并做联调。
