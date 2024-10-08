from typing import Optional
from sqlmodel import SQLModel, Field

class Gateway(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mac_address: str = Field(index=True)
    name: str
    x: float
    y: float
    z: float
    gw_type: str