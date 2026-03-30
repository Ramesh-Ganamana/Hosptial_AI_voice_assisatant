from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import io
import wave

# Import services
from services.sarvam_service import sarvam_service
from services.llm_service_db import LLMServiceDB
from services.doctor_service import doctor_service
from services.appointment_service import appointment_service
from services.db_init_service import initialize_database
from services.slot_service import SlotGenerationService
from services.appointment_service_db import AppointmentServiceDB


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize services
slot_service = SlotGenerationService(db)
appointment_service_db = AppointmentServiceDB(db)
llm_service_db = LLMServiceDB(db)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class ProcessAudioResponse(BaseModel):
    transcription: str
    response: str
    session_id: str

class BookAppointmentRequest(BaseModel):
    patient_name: str
    doctor_id: str
    doctor_name: str
    date: str
    time: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hospital AI Assistant API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of records to return"),
    skip: int = Query(default=0, ge=0, description="Number of records to skip")
):
    # Fetch status checks with pagination
    status_checks = await db.status_checks.find({}, {"_id": 0}).skip(skip).limit(limit).to_list(length=None)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

@api_router.post("/process-audio", response_model=ProcessAudioResponse)
async def process_audio(
    audio: UploadFile = File(...),
    session_id: Optional[str] = None
):
    """
    Process audio file: transcribe speech and generate AI response
    Uses Sarvam AI for Indian English speech recognition
    """
    try:
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Read audio file
        audio_data = await audio.read()
        
        logger.info(f"Processing audio: {len(audio_data)} bytes, format: {audio.content_type}")
        
        # Transcribe audio using Sarvam (cloud-based, no local models needed)
        transcription = sarvam_service.transcribe_audio(audio_data)
        
        if not transcription or transcription.strip() == "":
            return ProcessAudioResponse(
                transcription="",
                response="I didn't catch that. Could you please speak again?",
                session_id=session_id
            )
        
        logger.info(f"Transcription: {transcription}")
        
        # Get AI response using enhanced LLM with database context
        ai_response = await llm_service_db.process_message(session_id, transcription)
        
        return ProcessAudioResponse(
            transcription=transcription,
            response=ai_response,
            session_id=session_id
        )
    
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/book-appointment")
async def book_appointment(request: BookAppointmentRequest):
    """Book an appointment"""
    try:
        appointment = appointment_service.book_appointment(
            patient_name=request.patient_name,
            doctor_id=request.doctor_id,
            doctor_name=request.doctor_name,
            date=request.date,
            time=request.time
        )
        return {
            "success": True,
            "message": "Appointment booked successfully",
            "appointment": appointment
        }
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/doctors")
async def get_doctors():
    """Get all doctors from database"""
    try:
        doctors = await db.doctors.find(
            {"active_status": True},
            {"_id": 0}
        ).to_list(length=None)
        return {"doctors": doctors}
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return {"doctors": []}

@api_router.get("/doctors/by-department/{department_id}")
async def get_doctors_by_department(department_id: str):
    """Get doctors by department"""
    try:
        doctors = await db.doctors.find(
            {"department_id": department_id, "active_status": True},
            {"_id": 0}
        ).to_list(length=None)
        return {"doctors": doctors}
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return {"doctors": []}

@api_router.get("/departments")
async def get_departments():
    """Get all departments"""
    try:
        departments = await db.departments.find({}, {"_id": 0}).to_list(length=None)
        return {"departments": departments}
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return {"departments": []}

@api_router.get("/appointments/availability")
async def check_availability(
    doctor_id: str = Query(..., description="Doctor ID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """Check available slots for a doctor on a specific date"""
    try:
        availability = await slot_service.get_available_slots(doctor_id, date)
        return availability
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/appointments/book")
async def book_appointment_v2(
    doctor_id: str,
    patient_name: str,
    appointment_date: str,
    start_time: str,
    appointment_type: str = "Consultation"
):
    """Book an appointment with concurrency control"""
    try:
        result = await appointment_service_db.book_appointment(
            doctor_id=doctor_id,
            patient_name=patient_name,
            appointment_date=appointment_date,
            start_time=start_time,
            appointment_type=appointment_type
        )
        return result
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes liveness probe
    Returns 200 if the service is running
    """
    return {
        "status": "healthy",
        "service": "hospital-ai-assistant",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@api_router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes readiness probe
    Checks if all dependencies (MongoDB, external APIs) are accessible
    """
    try:
        # Check MongoDB connection
        await db.command("ping")
        
        return {
            "status": "ready",
            "service": "hospital-ai-assistant",
            "mongodb": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "mongodb": "disconnected",
                "error": str(e)
            }
        )

@api_router.get("/healthz")
async def kubernetes_health():
    """
    Alternative health endpoint (common Kubernetes convention)
    """
    return {"status": "ok"}

@api_router.get("/livez")
async def kubernetes_liveness():
    """
    Liveness endpoint for Kubernetes
    """
    return {"status": "alive"}

# Include the router in the main app
app.include_router(api_router)

# Custom 404 handler to handle security scanning probes gracefully
@app.exception_handler(404)
async def custom_404_handler(request, exc):
    """
    Custom 404 handler to gracefully handle security scanning attempts
    """
    path = request.url.path
    
    # List of common security probe paths
    security_probes = [
        '.env', 'config.env', 'config.map', 'config', 'settings',
        'stripe', 'payment', '.git', 'admin', 'phpmyadmin'
    ]
    
    # Check if this looks like a security probe
    is_probe = any(probe in path.lower() for probe in security_probes)
    
    if is_probe:
        # Return minimal response for security probes
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"}
        )
    
    # Return detailed 404 for legitimate requests
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Endpoint not found",
            "path": path,
            "available_endpoints": [
                "/api/",
                "/api/health",
                "/api/ready",
                "/api/doctors",
                "/api/process-audio",
                "/api/book-appointment",
                "/api/status"
            ]
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_db_client():
    """Initialize database on startup"""
    try:
        await initialize_database(db)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Root-level health endpoints (Kubernetes standard)
@app.get("/health")
async def root_health_check():
    """Root-level health check"""
    return {"status": "healthy", "service": "hospital-ai-assistant"}

@app.get("/healthz")
async def root_healthz():
    """Kubernetes standard health check"""
    return {"status": "ok"}

@app.get("/ready")
async def root_ready():
    """Root-level readiness check"""
    try:
        await db.command("ping")
        return {"status": "ready", "mongodb": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")