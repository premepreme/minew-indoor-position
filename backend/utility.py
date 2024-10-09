import json

from datetime import datetime, timezone, timedelta
import paho.mqtt.client as mqtt
from typing import Dict, List

class MQTTManager:
    def __init__(self):
        self.mqtt_client = None
        self.mqtt_data_store: Dict[str, List[Dict[str, str]]] = {}
        self.gateway_response_store: Dict[str, str] = {}
        self.gateway_config_store: Dict[str, str] = {}
        self.mac_data = {
            "devices": ["C300001AA631", "C3000014BBD8"],
            "gw": ["ac233fc18bef"],
            "mg3": ["ac233fc160f5", "ac233fc160e3"],
        }

    def initialize_mqtt(self, host: str, port: int, username: str, password: str):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.username_pw_set(username=username, password=password)
        self.mqtt_client.connect(host, port)
        self.mqtt_client.loop_start()
        print("MQTT client initialized:", self.mqtt_client)

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f"Connected with result code {reason_code}")
        self.subscribe_to_topics()

    def on_message(self, client, userdata, msg):
        data_str = msg.payload.decode("UTF-8")
        topic = msg.topic
        if "/response" in topic:
            gateway_mac = topic.split("/")[2]
            data = json.loads(data_str)
            if "currentConfig" in data:
                self.gateway_config_store[gateway_mac] = data["currentConfig"]
            else:
                self.gateway_response_store[gateway_mac] = data
        else:
            self.process_data(data_str)

    def process_data(self, data_str: str):
        for data in json.loads(data_str):
            if data.get("type") == "Gateway":
                pass
            elif data.get("type") is None or data.get("type") == "iBeacon":
                mac = data.get("mac").lower()
                self.mqtt_data_store.setdefault(mac, []).append(
                    {
                    "timestamp": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                        "mac": mac,
                        "rssi": data.get("rssi"),
                    }
                )
                if len(self.mqtt_data_store[mac]) > 100:
                    self.mqtt_data_store[mac] = self.mqtt_data_store[mac][-100:]

    def subscribe_to_topics(self):
        for mac in self.mac_data["mg3"]:
            self.mqtt_client.subscribe(f"/mg3/{mac}/status")
            self.mqtt_client.subscribe(f"/mg3/{mac}/response")
            print("Subscribed to", f"/mg3/{mac}")
        for mac in self.mac_data["gw"]:
            self.mqtt_client.subscribe(f"/gw/{mac}/status")
            self.mqtt_client.subscribe(f"/gw/{mac}/response")
            print("Subscribed to", f"/gw/{mac}")


mqtt_manager = MQTTManager()
