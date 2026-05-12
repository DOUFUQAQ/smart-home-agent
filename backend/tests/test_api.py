from __future__ import annotations


def create_device(client, name: str, device_type: str):
    response = client.post(
        "/api/devices",
        json={"name": name, "type": device_type, "location": "lab"},
    )
    assert response.status_code == 200
    return response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_device_create_and_update_state(client):
    light = create_device(client, "客厅主灯", "light")
    response = client.patch(
        f"/api/devices/{light['id']}/state",
        json={"status": "online", "state": {"power": "on"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "online"
    assert payload["state"]["power"] == "on"


def test_reading_create_and_alert_trigger(client):
    sensor = create_device(client, "环境传感器", "sensor")
    response = client.post(
        "/api/readings",
        json={
            "device_id": sensor["id"],
            "temperature": 34.2,
            "humidity": 45.0,
            "gas_ppm": 450.0,
        },
    )
    assert response.status_code == 200
    response = client.get("/api/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 2
    assert any("温度过高" in alert["message"] for alert in alerts)
    assert any("可燃气体浓度异常" in alert["message"] for alert in alerts)


def test_parse_command(client):
    response = client.post(
        "/api/llm/parse-command",
        json={"text": "请打开客厅主灯，再调亮一点"},
    )
    assert response.status_code == 200
    parsed = response.json()["commands"]
    actions = {item["action"] for item in parsed}
    assert "turn_on" in actions
    assert "set_brightness" in actions


def test_execute_command(client):
    _ = create_device(client, "客厅主灯", "light")
    response = client.post("/api/control/execute", json={"text": "打开客厅主灯"})
    assert response.status_code == 200
    updated = response.json()["updated_devices"]
    assert len(updated) == 1
    assert updated[0]["state"]["power"] == "on"


def test_demo_seed_and_reset(client):
    seed_response = client.post("/api/demo/seed")
    assert seed_response.status_code == 200
    payload = seed_response.json()
    assert payload["status"] == "ok"
    assert payload["counts"]["devices"] == 4
    assert payload["counts"]["readings"] == 6
    assert payload["counts"]["alerts"] >= 2
    assert len(payload["demo_commands"]) == 5

    devices = client.get("/api/devices").json()
    readings = client.get("/api/readings").json()
    alerts = client.get("/api/alerts").json()
    assert len(devices) == 4
    assert len(readings) == 6
    assert len(alerts) >= 2

    reset_response = client.post("/api/demo/reset")
    assert reset_response.status_code == 200
    assert client.get("/api/devices").json() == []
