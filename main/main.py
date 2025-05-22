
from fastapi import FastAPI, HTTPException, status
from typing import List
from datetime import datetime, date, timedelta
import uuid

from models import ChargingStation, Connector, ChargingSession, ChargingSessionCreate

app = FastAPI(
    title="MCP EV Charging Server",
    description="Backend for AI-powered EV charging network management."
)

# ---  In-Memory Storage (Replace with real DB in production) ---
mock_stations_db: List[ChargingStation] = [
    ChargingStation(
        station_id="STN-001",
        name="Downtown Fast Charger",
        location_coords=[34.0522, -118.2437], # Example LA coords
        address="123 Main St, Anytown",
        owner="EVChargeCo",
        connectors=[
            Connector(connector_id="C-001-1", type="CCS1", power_kw=50.0, status="available"),
            Connector(connector_id="C-001-2", type="J1772", power_kw=7.2, status="available"),
        ]
    ),
    ChargingStation(
        station_id="STN-002",
        name="Parkside L2 Chargers",
        location_coords=[34.0722, -118.2537],
        address="456 Oak Ave, Anytown",
        owner="CityPower",
        connectors=[
            Connector(connector_id="C-002-1", type="J1772", power_kw=7.2, status="available"),
            Connector(connector_id="C-002-2", type="J1772", power_kw=7.2, status="available"),
        ]
    ),
]
mock_sessions_db: List[ChargingSession] = []
# -------------------------------------------------------------------------

# Utility function  involve complex DB queries in reality)
def check_connector_availability(
    station_id: str,
    connector_id: str,
    start_time: datetime,
    end_time: datetime
) -> bool:
    """Checks if the given connector is available for the specified time slot."""
    for existing_session in mock_sessions_db:
        if (existing_session.station_id == station_id and
            existing_session.connector_id == connector_id and
            existing_session.status in ["reserved", "in_progress"]): # Only check active or reserved sessions
            # Check for time overlap
            if not (end_time <= existing_session.start_time or start_time >= existing_session.expected_end_time):
                return False # Overlap detected
    return True

# --- API Endpoints ---

@app.get("/stations", response_model=List[ChargingStation], summary="Get all charging stations")
async def get_charging_stations():
    """Retrieves a list of all defined charging stations in the system."""
    return mock_stations_db

@app.get("/stations/{station_id}", response_model=ChargingStation, summary="Get details of a specific charging station")
async def get_station_details(station_id: str):
    """Retrieves details for a specific charging station by ID."""
    station = next((s for s in mock_stations_db if s.station_id == station_id), None)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Charging station with ID '{station_id}' not found."
        )
    return station

@app.post("/sessions", response_model=ChargingSession, status_code=status.HTTP_201_CREATED, summary="Reserve a charging session")
async def create_charging_session(session_data: ChargingSessionCreate):
    """
    Creates a new charging session reservation for a specified connector and time slot.
    Performs availability check before confirming the reservation.
    """
    # 1. Input Validation (handled by Pydantic/FastAPI)
    # Ensure session is not in the past or invalid
    if session_data.expected_end_time <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reserve a session in the past."
        )
    if session_data.start_time >= session_data.expected_end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time."
        )

    # 2. Check Station & Connector Exist and are available
    target_station = next((s for s in mock_stations_db if s.station_id == session_data.station_id), None)
    if not target_station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Charging station with ID '{session_data.station_id}' not found."
        )
    target_connector = next(
        (c for c in target_station.connectors if c.connector_id == session_data.connector_id), None
    )
    if not target_connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector with ID '{session_data.connector_id}' not found at station '{session_data.station_id}'."
        )
    if target_connector.status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector {session_data.connector_id} is currently {target_connector.status}."
        )

    # 3. Check Availability (for reservations)
    if not check_connector_availability(
        session_data.station_id,
        session_data.connector_id,
        session_data.start_time,
        session_data.expected_end_time
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, # Conflict indicates resource is taken
            detail=f"Connector {session_data.connector_id} at {session_data.station_id} is not available during the requested time."
        )

    # 4. Create Reservation (in a real app, this would be a DB transaction)
    new_session_id = str(uuid.uuid4()) # Generate a unique ID
    new_session = ChargingSession(
        session_id=new_session_id,
        **session_data.dict(),
        status="reserved",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    mock_sessions_db.append(new_session)

    # In a real system, you'd now call out to the physical charging station
    # via its API (e.g., OCPP) to mark the connector as reserved.
    # For now, we'll simulate updating its status in our mock DB.
    target_connector.status = "reserved"


    # 5. Return Confirmation
    return new_session

@app.get("/sessions/user/{user_id}", response_model=List[ChargingSession], summary="Get charging sessions for a specific user")
async def get_user_sessions(user_id: str):
    """Retrieves all active or reserved charging sessions for a given user ID."""
    return [s for s in mock_sessions_db if s.user_id == user_id and s.status in ["reserved", "in_progress"]]

@app.put("/sessions/{session_id}/start", response_model=ChargingSession, summary="Start a reserved charging session")
async def start_charging_session(session_id: str):
    """Transitions a reserved session to in_progress."""
    session = next((s for s in mock_sessions_db if s.session_id == session_id), None)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if session.status != "reserved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not in 'reserved' status.")

    session.status = "in_progress"
    session.start_time = datetime.utcnow() # Actual start time
    session.updated_at = datetime.utcnow()

    # Update connector status to 'occupied'
    for station in mock_stations_db:
        if station.station_id == session.station_id:
            for connector in station.connectors:
                if connector.connector_id == session.connector_id:
                    connector.status = "occupied"
                    break
            break
    return session

@app.put("/sessions/{session_id}/end", response_model=ChargingSession, summary="End an in-progress charging session")
async def end_charging_session(session_id: str, kwh_consumed: float = 0.0, cost: float = 0.0):
    """Transitions an in-progress session to completed."""
    session = next((s for s in mock_sessions_db if s.session_id == session_id), None)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if session.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not in 'in_progress' status.")

    session.status = "completed"
    session.actual_end_time = datetime.utcnow()
    session.kwh_consumed = kwh_consumed
    session.cost = cost
    session.updated_at = datetime.utcnow()

    # Update connector status back to 'available'
    for station in mock_stations_db:
        if station.station_id == session.station_id:
            for connector in station.connectors:
                if connector.connector_id == session.connector_id:
                    connector.status = "available"
                    break
            break
    return session

@app.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel a reserved charging session")
async def cancel_charging_session(session_id: str):
    """Cancels an existing reserved charging session by its ID."""
    global mock_sessions_db # To modify the list
    session_found = False
    for i, session in enumerate(mock_sessions_db):
        if session.session_id == session_id:
            if session.status == "reserved":
                mock_sessions_db[i].status = "cancelled"
                mock_sessions_db[i].updated_at = datetime.utcnow()

                # Update connector status back to 'available'
                for station in mock_stations_db:
                    if station.station_id == session.station_id:
                        for connector in station.connectors:
                            if connector.connector_id == session.connector_id:
                                connector.status = "available"
                                break
                        break
                session_found = True
                break
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only 'reserved' sessions can be cancelled via this endpoint.")
    if not session_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
