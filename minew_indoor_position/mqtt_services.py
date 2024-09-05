import json

import paho.mqtt.client as mqtt
from core.config import settings
from db.services import enqueue

host = settings.MQTT_HOST
port = str(settings.MQTT_PORT)
mac_devices = settings.DEVICE_MACS
mac_gateways = settings.GATEWAY_MACS


def on_connect(client, userdata, flags, reason_code, properties):  # noqa: ARG001
    print(f"Connected with result code {reason_code}")

    for mac in mac_gateways:
        client.subscribe(f"/mg3/{mac}/status")


def on_message(client, userdata, msg):  # noqa: ARG001
    data_str = str(msg.payload.decode("UTF-8"))
    for data in json.loads(data_str):
        if data.get("type") == "Gateway":
            pass
        elif data.get("type") is None:
            if data.get("mac") in mac_devices:
                gateway_name = str(msg.topic).split("/")[2]
                device_name = data.get("mac")
                enqueue(value=data.get("rssi"), key=f"{device_name}_{gateway_name}")


if __name__ == "__main__":
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.username_pw_set(username="erudite", password="Erud1t3wifi")

    mqttc.connect(host=host, port=int(port))

    mqttc.loop_forever()
