
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field

class Connector(BaseModel):
    connector_id: str
    type: str # e.g., 'J1772', 'CCS1', 'CCS2', 'CHAdeMO', 'Tesla'
    power_kw: float # e.g., 7.2, 50.0, 150.0
    status: str = "available" # 'available', 'occupied', 'out_of_service'

class ChargingStationBase(BaseModel):
    name: str
    location_coords: List[float] = Field(..., min_items=2, max_items=2) # [latitude, longitude]
    address: str
    owner: str # e.g., 'ChargePoint', 'Electrify America', 'Tesla Supercharger'
    is_public: bool = True
    connectors: List[Connector] = [] # List of available connectors

class ChargingStation(ChargingStationBase):
    station_id: str
    overall_status: str = "active" # 'active', 'offline', 'maintenance'

    class Config:
        orm_mode = True # Enables ORM compatibility

class ChargingSessionBase(BaseModel):
    station_id: str
    connector_id: str
    user_id: str # EV owner ID or similar
    start_time: datetime
    expected_end_time: datetime # Estimated end time for reservation purposes

class ChargingSessionCreate(ChargingSessionBase):
    pass # No extra fields for creation currently

class ChargingSession(ChargingSessionBase):
    session_id: str
    actual_end_time: Optional[datetime] = None
    kwh_consumed: Optional[float] = None
    cost: Optional[float] = None
    status: str = "reserved" # 'reserved', 'in_progress', 'completed', 'cancelled', 'failed'
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
