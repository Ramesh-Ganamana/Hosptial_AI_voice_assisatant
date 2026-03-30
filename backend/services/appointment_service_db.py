"""
Enhanced Appointment Service with Database Integration
Handles appointment booking, rescheduling, and cancellation
with proper concurrency control
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid

logger = logging.getLogger(__name__)

class AppointmentServiceDB:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def book_appointment(
        self,
        doctor_id: str,
        patient_name: str,
        appointment_date: str,
        start_time: str,
        appointment_type: str = "Consultation",
        patient_id: Optional[str] = None
    ) -> Dict:
        """
        Book an appointment with concurrency control
        
        Args:
            doctor_id: Doctor ID
            patient_name: Patient name
            appointment_date: Date in YYYY-MM-DD format
            start_time: Time in HH:MM format
            appointment_type: Type of appointment
            patient_id: Optional patient ID
        
        Returns:
            Dict with booking result
        """
        try:
            # Generate IDs
            if not patient_id:
                patient_id = f"PAT_{uuid.uuid4().hex[:8].upper()}"
            
            appointment_id = f"APT_{uuid.uuid4().hex[:8].upper()}"
            
            # Calculate end time (15 minutes later)
            from datetime import datetime, timedelta, time
            hour, minute = map(int, start_time.split(':'))
            start_dt = datetime.combine(datetime.today(), time(hour, minute))
            end_dt = start_dt + timedelta(minutes=15)
            end_time = end_dt.strftime("%H:%M")
            
            # CRITICAL: Use atomic operation to prevent double booking
            # Try to insert only if no conflicting appointment exists
            existing = await self.db.appointments.find_one({
                "doctor_id": doctor_id,
                "appointment_date": appointment_date,
                "start_time": start_time,
                "status": {"$in": ["CONFIRMED", "PENDING"]}
            })
            
            if existing:
                return {
                    "success": False,
                    "error": "SLOT_ALREADY_BOOKED",
                    "message": "That slot has just been booked by another patient. Please choose another available time."
                }
            
            # Create appointment document
            appointment = {
                "appointment_id": appointment_id,
                "doctor_id": doctor_id,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "appointment_date": appointment_date,
                "start_time": start_time,
                "end_time": end_time,
                "appointment_type": appointment_type,
                "status": "CONFIRMED",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert appointment
            result = await self.db.appointments.insert_one(appointment)
            
            if result.inserted_id:
                # Get doctor details
                doctor = await self.db.doctors.find_one({"doctor_id": doctor_id})
                
                return {
                    "success": True,
                    "appointment_id": appointment_id,
                    "doctor_name": doctor.get("doctor_name") if doctor else "Doctor",
                    "patient_name": patient_name,
                    "appointment_date": appointment_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "status": "CONFIRMED",
                    "message": f"Your appointment with {doctor.get('doctor_name') if doctor else 'the doctor'} is confirmed for {appointment_date} at {start_time}."
                }
            else:
                return {
                    "success": False,
                    "error": "BOOKING_FAILED",
                    "message": "Failed to book appointment. Please try again."
                }
        
        except Exception as e:
            logger.error(f"Error booking appointment: {e}", exc_info=True)
            return {
                "success": False,
                "error": "SYSTEM_ERROR",
                "message": f"An error occurred: {str(e)}"
            }
    
    async def cancel_appointment(self, appointment_id: str) -> Dict:
        """Cancel an appointment"""
        try:
            result = await self.db.appointments.update_one(
                {"appointment_id": appointment_id},
                {
                    "$set": {
                        "status": "CANCELLED",
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                return {
                    "success": True,
                    "message": "Appointment cancelled successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Appointment not found"
                }
        
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    async def reschedule_appointment(
        self,
        appointment_id: str,
        new_date: str,
        new_time: str
    ) -> Dict:
        """Reschedule an existing appointment"""
        try:
            # Get existing appointment
            appointment = await self.db.appointments.find_one({"appointment_id": appointment_id})
            
            if not appointment:
                return {
                    "success": False,
                    "message": "Appointment not found"
                }
            
            # Check if new slot is available
            from .slot_service import SlotGenerationService
            slot_service = SlotGenerationService(self.db)
            
            availability = await slot_service.is_slot_available(
                appointment["doctor_id"],
                new_date,
                new_time
            )
            
            if not availability["available"]:
                return {
                    "success": False,
                    "message": availability["reason"],
                    "next_available": availability.get("next_available", [])
                }
            
            # Calculate new end time
            from datetime import datetime, timedelta, time
            hour, minute = map(int, new_time.split(':'))
            start_dt = datetime.combine(datetime.today(), time(hour, minute))
            end_dt = start_dt + timedelta(minutes=15)
            new_end_time = end_dt.strftime("%H:%M")
            
            # Update appointment
            result = await self.db.appointments.update_one(
                {"appointment_id": appointment_id},
                {
                    "$set": {
                        "appointment_date": new_date,
                        "start_time": new_time,
                        "end_time": new_end_time,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                return {
                    "success": True,
                    "message": f"Appointment rescheduled to {new_date} at {new_time}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to reschedule appointment"
                }
        
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    async def get_appointments_by_doctor(
        self,
        doctor_id: str,
        date: Optional[str] = None
    ) -> List[Dict]:
        """Get all appointments for a doctor"""
        try:
            query = {
                "doctor_id": doctor_id,
                "status": {"$in": ["CONFIRMED", "PENDING"]}
            }
            
            if date:
                query["appointment_date"] = date
            
            appointments = await self.db.appointments.find(query).to_list(length=None)
            return appointments
        
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}")
            return []
    
    async def add_surgery_block(
        self,
        doctor_id: str,
        surgery_date: str,
        surgery_start_time: str,
        surgery_end_time: str,
        surgery_type: str = "Surgery"
    ) -> Dict:
        """Add a surgery block for a doctor"""
        try:
            surgery_id = f"SRG_{uuid.uuid4().hex[:8].upper()}"
            
            surgery_block = {
                "surgery_block_id": surgery_id,
                "doctor_id": doctor_id,
                "surgery_date": surgery_date,
                "surgery_start_time": surgery_start_time,
                "surgery_end_time": surgery_end_time,
                "surgery_type": surgery_type,
                "status": "SURGERY_BLOCK",
                "created_at": datetime.utcnow().isoformat()
            }
            
            result = await self.db.surgery_blocks.insert_one(surgery_block)
            
            if result.inserted_id:
                return {
                    "success": True,
                    "surgery_id": surgery_id,
                    "message": f"Surgery block added from {surgery_start_time} to {surgery_end_time}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to add surgery block"
                }
        
        except Exception as e:
            logger.error(f"Error adding surgery block: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    async def add_doctor_absence(
        self,
        doctor_id: str,
        absent_date: str,
        reason: str = "Not available"
    ) -> Dict:
        """Mark a doctor as absent for a day"""
        try:
            absence_id = f"ABS_{uuid.uuid4().hex[:8].upper()}"
            
            absence = {
                "absence_id": absence_id,
                "doctor_id": doctor_id,
                "absent_date": absent_date,
                "reason": reason,
                "status": "ABSENT",
                "created_at": datetime.utcnow().isoformat()
            }
            
            result = await self.db.doctor_absence.insert_one(absence)
            
            if result.inserted_id:
                return {
                    "success": True,
                    "absence_id": absence_id,
                    "message": f"Doctor marked absent for {absent_date}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to mark absence"
                }
        
        except Exception as e:
            logger.error(f"Error adding absence: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
