from fastapi import FastAPI
from router import combined_router
from contextlib import asynccontextmanager
from utility import mqtt_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_manager.initialize_mqtt(
        host="122.8.155.113", port=1883, username="erudite", password="Erud1t3wifi"
    )
    print("MQTT client started and subscribed.")

    yield

    if mqtt_manager.mqtt_client:
        mqtt_manager.mqtt_client.loop_stop()
        mqtt_manager.mqtt_client.disconnect()
        print("MQTT client disconnected.")


app = FastAPI(lifespan=lifespan)
app.include_router(combined_router, tags=["Gateway and MAC Endpoints"])


@app.get("/")
async def root():
    return {"message": "FastAPI and MQTT client are running"}
