from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Query
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
from services.llm_service import llm_service
from services.doctor_service import doctor_service
from services.appointment_service import appointment_service


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
        
        # Get AI response using LLM
        ai_response = await llm_service.process_message(session_id, transcription)
        
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
    """Get all doctors"""
    doctors = doctor_service.get_all_doctors()
    return {"doctors": doctors}

# Include the router in the main app
app.include_router(api_router)

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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()