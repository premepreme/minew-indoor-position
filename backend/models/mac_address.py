from typing import Optional
from sqlmodel import SQLModel, Field


class MACAddress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True) 
    category: str
    mac_address: str
    name: str
    x: float
    y: float
    z: float
