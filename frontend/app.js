const storageKey = "smart-home-api-base";
const defaultDemoCommands = [
  "打开客厅主灯",
  "关闭卧室插座",
  "打开风扇",
  "如果温度超过30度就打开风扇",
  "把客厅主灯调亮一点",
];

let apiBase = localStorage.getItem(storageKey) || "http://127.0.0.1:8000";

const apiBaseInput = document.getElementById("apiBase");
const messageBox = document.getElementById("messageBox");
const devicesList = document.getElementById("devicesList");
const readingDeviceId = document.getElementById("readingDeviceId");
const alertsList = document.getElementById("alertsList");
const readingsList = document.getElementById("readingsList");
const parseResult = document.getElementById("parseResult");
const executeResult = document.getElementById("executeResult");
const parseTextInput = document.getElementById("parseText");
const executeTextInput = document.getElementById("executeText");
const demoCommandsBox = document.getElementById("demoCommands");

apiBaseInput.value = apiBase;

function showMessage(message, isError = false) {
  messageBox.textContent = message;
  messageBox.style.color = isError ? "#b91c1c" : "#0f766e";
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`请求失败 ${response.status}: ${errText}`);
  }
  return response.json();
}

function renderDemoCommands(commands = defaultDemoCommands) {
  demoCommandsBox.innerHTML = "";
  commands.forEach((command) => {
    const button = document.createElement("button");
    button.className = "command-chip";
    button.type = "button";
    button.textContent = command;
    button.onclick = () => {
      parseTextInput.value = command;
      executeTextInput.value = command;
      showMessage(`已填入演示命令：${command}`);
    };
    demoCommandsBox.appendChild(button);
  });
}

function renderDevices(devices) {
  devicesList.innerHTML = "";
  readingDeviceId.innerHTML = "";

  if (!devices.length) {
    devicesList.innerHTML = '<div class="item">暂无设备，请先新增设备或加载演示数据。</div>';
    return;
  }

  devices.forEach((device) => {
    const option = document.createElement("option");
    option.value = device.id;
    option.textContent = `${device.name} (${device.type})`;
    readingDeviceId.appendChild(option);

    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `
      <div><strong>${device.name}</strong> [${device.type}] - ${device.location}</div>
      <div>状态：${device.status} | 当前值：${JSON.stringify(device.state)}</div>
    `;

    const actions = document.createElement("div");
    actions.className = "item-actions";
    const onBtn = document.createElement("button");
    onBtn.textContent = "打开";
    onBtn.onclick = () =>
      quickUpdateDevice(device.id, { status: "online", state: { power: "on" } });
    const offBtn = document.createElement("button");
    offBtn.textContent = "关闭";
    offBtn.onclick = () =>
      quickUpdateDevice(device.id, { status: "online", state: { power: "off" } });
    actions.appendChild(onBtn);
    actions.appendChild(offBtn);
    item.appendChild(actions);
    devicesList.appendChild(item);
  });
}

function renderAlerts(alerts) {
  alertsList.innerHTML = "";
  if (!alerts.length) {
    alertsList.innerHTML = '<div class="item">暂无告警。</div>';
    return;
  }
  alerts.forEach((alert) => {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent = `[${alert.level}] ${alert.message} (${alert.device_id})`;
    alertsList.appendChild(item);
  });
}

function renderReadings(readings) {
  readingsList.innerHTML = "";
  if (!readings.length) {
    readingsList.innerHTML = '<div class="item">暂无历史数据。</div>';
    return;
  }
  readings.forEach((reading) => {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent =
      `${reading.created_at} | 设备:${reading.device_id} | ` +
      `T:${reading.temperature} | H:${reading.humidity} | G:${reading.gas_ppm}`;
    readingsList.appendChild(item);
  });
}

async function loadDevices() {
  const devices = await request("/api/devices");
  renderDevices(devices);
}

async function loadAlerts() {
  const alerts = await request("/api/alerts");
  renderAlerts(alerts);
}

async function loadReadings() {
  const readings = await request("/api/readings");
  renderReadings(readings);
}

async function refreshAllData() {
  await Promise.all([loadDevices(), loadAlerts(), loadReadings()]);
}

async function quickUpdateDevice(deviceId, payload) {
  try {
    await request(`/api/devices/${deviceId}/state`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    showMessage("设备状态更新成功");
    await loadDevices();
  } catch (error) {
    showMessage(error.message, true);
  }
}

document.getElementById("saveBaseBtn").addEventListener("click", async () => {
  apiBase = apiBaseInput.value.trim().replace(/\/+$/, "");
  localStorage.setItem(storageKey, apiBase);
  showMessage(`已保存后端地址：${apiBase}`);
  try {
    await request("/health");
    await refreshAllData();
  } catch (error) {
    showMessage(`后端连接失败：${error.message}`, true);
  }
});

document.getElementById("seedDemoBtn").addEventListener("click", async () => {
  try {
    const data = await request("/api/demo/seed", { method: "POST" });
    renderDemoCommands(data.demo_commands || defaultDemoCommands);
    await refreshAllData();
    showMessage(
      `演示数据已加载：设备 ${data.counts.devices} 个，读数 ${data.counts.readings} 条，告警 ${data.counts.alerts} 条`
    );
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("resetDemoBtn").addEventListener("click", async () => {
  try {
    await request("/api/demo/reset", { method: "POST" });
    await refreshAllData();
    renderDemoCommands(defaultDemoCommands);
    parseResult.textContent = "";
    executeResult.textContent = "";
    showMessage("演示数据已清空");
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("createDeviceForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await request("/api/devices", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("deviceName").value.trim(),
        type: document.getElementById("deviceType").value,
        location: document.getElementById("deviceLocation").value.trim() || "lab",
      }),
    });
    showMessage("设备新增成功");
    event.target.reset();
    document.getElementById("deviceLocation").value = "lab";
    await loadDevices();
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("readingForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const temperatureValue = document.getElementById("temperature").value;
    const humidityValue = document.getElementById("humidity").value;
    const gasValue = document.getElementById("gasPpm").value;

    await request("/api/readings", {
      method: "POST",
      body: JSON.stringify({
        device_id: readingDeviceId.value,
        temperature: temperatureValue ? Number(temperatureValue) : null,
        humidity: humidityValue ? Number(humidityValue) : null,
        gas_ppm: gasValue ? Number(gasValue) : null,
      }),
    });
    showMessage("数据上报成功");
    event.target.reset();
    await Promise.all([loadAlerts(), loadReadings()]);
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("parseForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const text = parseTextInput.value.trim();
    const data = await request("/api/llm/parse-command", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    parseResult.textContent = JSON.stringify(data, null, 2);
    showMessage("指令解析完成");
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("executeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const text = executeTextInput.value.trim();
    const data = await request("/api/control/execute", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    executeResult.textContent = JSON.stringify(data, null, 2);
    showMessage("指令执行完成");
    await loadDevices();
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("refreshDevicesBtn").addEventListener("click", () => loadDevices());
document.getElementById("refreshAlertsBtn").addEventListener("click", () => loadAlerts());
document.getElementById("refreshReadingsBtn").addEventListener("click", () => loadReadings());

async function init() {
  renderDemoCommands(defaultDemoCommands);
  try {
    await request("/health");
    showMessage("后端连接成功");
    await refreshAllData();
  } catch (error) {
    showMessage(`初始化失败，请检查后端：${error.message}`, true);
  }
}

init();
