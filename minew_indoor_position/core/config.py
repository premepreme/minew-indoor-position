from typing import Annotated, Any

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def gateway_parse_cors(v: Any) -> list[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip().lower() for i in v.split(",")]
    elif isinstance(v, list):
        return [i.lower() for i in v]
    elif isinstance(v, str):
        return [v.lower()]
    raise ValueError(v)


def device_parse_cors(v: Any) -> list[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip().upper() for i in v.split(",")]
    elif isinstance(v, list):
        return [i.upper() for i in v]
    elif isinstance(v, str):
        return [v.upper()]
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_ignore_empty=True, extra="ignore"
    )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    MAX_QUEUE_LENGTH: int = 10
    REDIS_DB: int = 0

    # MQTT
    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 1883

    # MAC Addresses
    GATEWAY_MACS: Annotated[list[str] | str, BeforeValidator(gateway_parse_cors)] = []
    MG3_MACS: Annotated[list[str] | str, BeforeValidator(gateway_parse_cors)] = []
    DEVICE_MACS: Annotated[list[str] | str, BeforeValidator(device_parse_cors)] = []


settings = Settings()
