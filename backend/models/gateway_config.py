from typing import Optional

from pydantic import BaseModel


class GatewayConfig(BaseModel):
    rssi: Optional[str] = None
    regex_mac: Optional[str] = None
