import json
import uuid
from datetime import datetime
from threading import Thread
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine

app = FastAPI()

# In-memory database for MAC addresses
mac_data = {
    "devices": ["C300001AA631", "C3000014BBD8"],
    "gw": ["ac233fc18bef"],
    "mg3": ["ac233fc160f5", "ac233fc160e3"],
}

mqtt_data_store: Dict[str, List[Dict[str, str]]] = {}
gateway_response_store: Dict[str, str] = {}
mqtt_client = None
gateway_config_store = {}

# SQLite setup
DATABASE_URL = "sqlite:///./gateway_data.db"
engine = create_engine(DATABASE_URL)


class Gateway(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)  # Allow custom id
    mac_address: str
    name: str
    x: float
    y: float
    z: float
    gw_type: str


SQLModel.metadata.create_all(engine)


class MACAddress(BaseModel):
    id: Optional[str]  # Add an optional id field
    category: str
    mac_address: str
    name: str
    x: float
    y: float
    z: float


# Define model for the configuration data
class GatewayConfig(BaseModel):
    rssi: Optional[str] = None
    regex_mac: Optional[str] = None


def fetch_mac_addresses():
    return mac_data


def subscribe_to_mqtt_topics(mac_gateways, mac_mg3):
    global mqtt_client
    if mqtt_client:
        # Subscribe to topics for new MAC addresses
        for mac in mac_mg3:
            mqtt_client.subscribe(f"/mg3/{mac}/status")
            mqtt_client.subscribe(f"/mg3/{mac}/response")
        for mac in mac_gateways:
            mqtt_client.subscribe(f"/gw/{mac}/status")
            mqtt_client.subscribe(f"/gw/{mac}/response")


def on_connect(client, userdata, flags, reason_code, properties):  # noqa: ARG001
    print(f"Connected with result code {reason_code}")
    mac_gateways = mac_data["gw"]
    mac_mg3 = mac_data["mg3"]
    subscribe_to_mqtt_topics(mac_gateways, mac_mg3)


def on_message(client, userdata, msg):  # noqa: ARG001
    data_str = str(msg.payload.decode("UTF-8"))
    topic = msg.topic

    if "/response" in topic:
        gateway_mac = topic.split("/")[2]
        data_str = json.loads(data_str)

        if (
            "currentConfig" in data_str
        ):  # Check if the message contains configuration details
            # Handle configuration details
            gateway_config_store[gateway_mac] = data_str["currentConfig"]
            print(
                f"Received configuration details from gateway {gateway_mac}: {data_str}"
            )
        else:
            # Handle online status or error response
            gateway_response_store[gateway_mac] = data_str
            print(f"Received status response from gateway {gateway_mac}: {data_str}")

    else:
        for data in json.loads(data_str):
            if data.get("type") == "Gateway":
                pass
            elif data.get("type") is None or data.get("type") == "iBeacon":
                mac = data.get("mac").lower()
                rssi = data.get("rssi")
                rawData = data.get("rawData")
                timestamp = datetime.utcnow().isoformat()

                # Store the data in a structured way
                if mac not in mqtt_data_store:
                    mqtt_data_store[mac] = []

                mqtt_data_store[mac].append(
                    {
                        "timestamp": timestamp,
                        "mac": mac.lower(),
                        "rssi": rssi,
                        "rawData": rawData,
                    }
                )

                if len(mqtt_data_store[mac]) > 100:
                    mqtt_data_store[mac] = mqtt_data_store[mac][
                        -100:
                    ]  # Keep only the last 100 records

        # print(f"Received message: {msg.payload.decode('utf-8')}")


def start_mqtt_client():
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.username_pw_set(username="erudite", password="Erud1t3wifi")
    mqtt_client.connect(host="122.8.155.113", port=1883)
    mqtt_client.loop_forever()


# Run MQTT client in a separate thread so FastAPI can serve while MQTT is running
@app.on_event("startup")
async def startup_event():
    mqtt_thread = Thread(target=start_mqtt_client)
    mqtt_thread.start()


@app.get("/")
async def root():
    return {"message": "FastAPI and MQTT client are running"}


@app.get("/macs")
async def get_macs():
    return mac_data


@app.post("/macs")
async def add_mac(mac: MACAddress):
    category = mac.category
    mac_address = mac.mac_address

    if category not in mac_data:
        raise HTTPException(
            status_code=400, detail="Invalid category. Must be  'gw', or 'mg3'."
        )

    if mac_address in mac_data[category]:
        raise HTTPException(
            status_code=400,
            detail=f"MAC address {mac_address} already exists in {category}.",
        )

    mac_data[category].append(mac_address)
    print(f"Added new MAC address {mac_address} to {category}")

    # Insert the new gateway into the SQLite database
    with Session(engine) as session:
        new_gateway = Gateway(
            id=mac.id,
            mac_address=mac.mac_address,
            name=mac.name,
            x=mac.x,
            y=mac.y,
            z=mac.z,
            gw_type=mac.category,
        )
        session.add(new_gateway)
        session.commit()

    # Dynamically subscribe to the new topic for this MAC address
    if category == "gw":
        mqtt_client.subscribe(f"/gw/{mac_address}/status")
        mqtt_client.subscribe(f"/gw/{mac_address}/response")
    elif category == "mg3":
        mqtt_client.subscribe(f"/mg3/{mac_address}/status")
        mqtt_client.subscribe(f"/mg3{mac_address}/response")

    return {
        "message": f"MAC address {mac_address} added to {category} and gateway information stored in the database."
    }


@app.delete("/macs/{category}/{mac_address}")
async def delete_mac(category: str, mac_address: str):
    if category not in mac_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid category. Must be 'devices', 'gw', or 'mg3'.",
        )

    if mac_address not in mac_data[category]:
        raise HTTPException(
            status_code=404,
            detail=f"MAC address {mac_address} not found in {category}.",
        )

    mac_data[category].remove(mac_address)
    print(f"Removed MAC address {mac_address} from {category}")

    # Unsubscribe from the MQTT topic for this MAC address
    if mqtt_client:
        if category == "devices":
            mqtt_client.unsubscribe(f"/device/{mac_address}/status")
        elif category == "gw":
            mqtt_client.unsubscribe(f"/gw/{mac_address}/status")
            mqtt_client.unsubscribe(f"/gw/{mac_address}/response")
        elif category == "mg3":
            mqtt_client.unsubscribe(f"/mg3/{mac_address}/status")

    with Session(engine) as session:
        gateway = session.query(Gateway).filter_by(mac_address=mac_address).first()
        if gateway:
            session.delete(gateway)
            session.commit()

    return {
        "message": f"MAC address {mac_address} removed from {category} and gateway information deleted from the database."
    }


@app.get("/macs/data/{mac}")
async def get_mac_data(mac: str):
    if mac not in mqtt_data_store:
        raise HTTPException(
            status_code=404, detail=f"No data found for MAC address {mac}."
        )
    return mqtt_data_store[mac]


@app.get("/macs/all_data")
async def get_all_mac_data():
    return mqtt_data_store


@app.post("/check-online/{gateway_mac}")
async def check_gateway(gateway_mac: str):
    request_id = str(uuid.uuid4())  # Generate random UUID for requestId
    message = {"code": 200, "message": "success", "requestId": request_id}

    # Check if the MAC address belongs to a gateway (gw) or mg3
    if gateway_mac in mac_data["gw"]:
        mqtt_client.publish(
            f"/gw/{gateway_mac}/action", json.dumps(message)
        )  # Publish to the gateway topic
    elif gateway_mac in mac_data["mg3"]:
        mqtt_client.publish(
            f"/mg3/{gateway_mac}/action", json.dumps(message)
        )  # Publish to the mg3 topic
    else:
        raise HTTPException(
            status_code=404,
            detail=f"MAC address {gateway_mac} not found in 'gw' or 'mg3'.",
        )

    return {
        "message": f"Heartbeat message sent to gateway {gateway_mac}",
        "requestId": request_id,
    }


@app.get("/check-online/{gateway_mac}")
async def get_gateway_status(gateway_mac: str):
    if gateway_mac in gateway_response_store:
        response = gateway_response_store[gateway_mac]
        return {"gateway_mac": gateway_mac, "status": "online", "response": response}
    else:
        return {"gateway_mac": gateway_mac, "status": "offline"}


@app.get("/gateway/config/{gateway_mac}")
async def get_gateway_config(gateway_mac: str):
    request_id = str(uuid.uuid4())

    # Prepare the MQTT message to request configuration
    message = {"action": "getConfig", "requestId": request_id}
    # Publish the message to the gateway's action topic
    mqtt_client.publish(f"/gw/{gateway_mac}/action", json.dumps(message))
    if gateway_mac in gateway_config_store:
        response = gateway_config_store[gateway_mac]
    return response


@app.put("/gateway/config/{gateway_mac}")
async def set_gateway_config(gateway_mac: str, config: GatewayConfig):
    request_id = str(uuid.uuid4())

    # Prepare the MQTT message for gateway configuration
    message = {
        "action": "config",
        "takeEffectImmediately": "YES",
        "filter": {
            "params": {
                "rssi": config.rssi,
                "regex_mac": config.regex_mac,
            }
        },
        "requestId": request_id,
    }

    # Save the configuration in the store for future retrieval via GET
    gateway_config_store[gateway_mac] = config.dict()

    # Publish the configuration message to the gateway's action topic
    mqtt_client.publish(f"/gw/{gateway_mac}/action", json.dumps(message))

    return {
        "message": f"Configuration set for gateway {gateway_mac}.",
        "requestId": request_id,
    }
