from fastapi import APIRouter, HTTPException
from sqlmodel import Session, create_engine
import json
import uuid
from models.gateway_config import GatewayConfig
from models.mac_address import MACAddress
from utility import mqtt_manager
from models.gateway import Gateway

DATABASE_URL = "sqlite:///./gateway_data.db"
engine = create_engine(DATABASE_URL)
combined_router = APIRouter()

@combined_router.get("/macs")
async def get_macs():
    return mqtt_manager.mac_data

@combined_router.post("/macs")
async def add_mac(mac: MACAddress):
    if mqtt_manager.mqtt_client is None:
        raise HTTPException(status_code=500, detail="MQTT client is not initialized.")
    category = mac.category
    mac_address = mac.mac_address

    if category not in mqtt_manager.mac_data:
        raise HTTPException(status_code=400, detail="Invalid category. Must be 'gw' or 'mg3'.")

    if mac_address in mqtt_manager.mac_data[category]:
        raise HTTPException(status_code=400, detail=f"MAC address {mac_address} already exists in {category}.")

    mqtt_manager.mac_data[category].append(mac_address)

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

    if category == "gw":
        mqtt_manager.mqtt_client.subscribe(f"/gw/{mac_address}/status")
        mqtt_manager.mqtt_client.subscribe(f"/gw/{mac_address}/response")
    elif category == "mg3":
        mqtt_manager.mqtt_client.subscribe(f"/mg3/{mac_address}/status")
        mqtt_manager.mqtt_client.subscribe(f"/mg3/{mac_address}/response")

    return {"message": f"MAC address {mac_address} added to {category}"}

@combined_router.delete("/macs/{category}/{mac_address}")
async def delete_mac(category: str, mac_address: str):
    if category not in mqtt_manager.mac_data or mac_address not in mqtt_manager.mac_data[category]:
        raise HTTPException(status_code=404, detail=f"MAC address {mac_address} not found in {category}.")

    mqtt_manager.mac_data[category].remove(mac_address)

    # Remove from the database
    with Session(engine) as session:
        gateway = session.query(Gateway).filter_by(mac_address=mac_address).first()
        if gateway:
            session.delete(gateway)
            session.commit()
            print(f"Removed {mac_address} from the database.")

    if category == "gw":
        mqtt_manager.mqtt_client.unsubscribe(f"/gw/{mac_address}/status")
        mqtt_manager.mqtt_client.unsubscribe(f"/gw/{mac_address}/response")
    elif category == "mg3":
        mqtt_manager.mqtt_client.unsubscribe(f"/mg3/{mac_address}/status")
        mqtt_manager.mqtt_client.unsubscribe(f"/mg3/{mac_address}/response")

    return {"message": f"MAC address {mac_address} removed from {category}"}


@combined_router.post("/gateway/check-online/{gateway_mac}")
async def check_gateway(gateway_mac: str):
    request_id = str(uuid.uuid4())
    message = {"code": 200, "message": "success", "requestId": request_id}

    if gateway_mac in mqtt_manager.mac_data["gw"]:
        mqtt_manager.mqtt_client.publish(f"/gw/{gateway_mac}/action", json.dumps(message))
    elif gateway_mac in mqtt_manager.mac_data["mg3"]:
        mqtt_manager.mqtt_client.publish(f"/mg3/{gateway_mac}/action", json.dumps(message))
    else:
        raise HTTPException(status_code=404, detail=f"MAC address {gateway_mac} not found in 'gw' or 'mg3'.")

    return {"message": f"Heartbeat message sent to gateway {gateway_mac}", "requestId": request_id}

@combined_router.get("/gateway/check-online/{gateway_mac}")
async def get_gateway_status(gateway_mac: str):
    if gateway_mac in mqtt_manager.gateway_response_store:
        response = mqtt_manager.gateway_response_store[gateway_mac]
        return {"gateway_mac": gateway_mac, "status": "online", "response": response}
    else:
        return {"gateway_mac": gateway_mac, "status": "offline"}

@combined_router.get("/gateway/config/{gateway_mac}")
async def get_gateway_config(gateway_mac: str):
    if gateway_mac in mqtt_manager.gateway_config_store:
        return {"gateway_mac": gateway_mac, "config": mqtt_manager.gateway_config_store[gateway_mac]}

    request_id = str(uuid.uuid4())
    message = {"action": "getConfig", "requestId": request_id}

    mqtt_manager.mqtt_client.publish(f"/gw/{gateway_mac}/action", json.dumps(message))
    return {"message": f"Configuration request sent to gateway {gateway_mac}", "requestId": request_id}


@combined_router.put("/gateway/config/{gateway_mac}")
async def set_gateway_config(gateway_mac: str, config: GatewayConfig):
    request_id = str(uuid.uuid4())

    # Initialize or retrieve the full config
    if gateway_mac in mqtt_manager.gateway_config_store:
        full_config = mqtt_manager.gateway_config_store[gateway_mac]
    else:
        raise HTTPException(status_code=404, detail="Gateway configuration not found.")
    
    # Only update the rssi and regex_mac in the filter section
    filter_params = full_config.get("filter", {}).get("params", {})
    filter_params["rssi"] = config.rssi if config.rssi is not None else filter_params.get("rssi")
    filter_params["regex_mac"] = config.regex_mac if config.regex_mac is not None else filter_params.get("regex_mac")

    # Update the full config with the modified filter params
    full_config["filter"]["params"] = filter_params
    mqtt_manager.gateway_config_store[gateway_mac] = full_config

    # Prepare the MQTT message to update the configuration
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
    
    # Publish the message to the gateway's action topic
    mqtt_manager.mqtt_client.publish(f"/gw/{gateway_mac}/action", json.dumps(message))
    
    # Return the entire updated configuration
    return {
        "message": f"Configuration updated for gateway {gateway_mac}.",
        "requestId": request_id,
        "config": full_config
    }

