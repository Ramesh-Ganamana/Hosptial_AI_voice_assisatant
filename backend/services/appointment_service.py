import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class AppointmentService:
    def __init__(self):
        # In-memory storage for appointments (in production, use a database)
        self.appointments: List[Dict] = []
    
    def book_appointment(self, 
                        patient_name: str,
                        doctor_id: str,
                        doctor_name: str,
                        date: str,
                        time: str) -> Dict:
        """Book an appointment"""
        try:
            appointment = {
                'id': f"apt_{len(self.appointments) + 1}",
                'patient_name': patient_name,
                'doctor_id': doctor_id,
                'doctor_name': doctor_name,
                'date': date,
                'time': time,
                'booked_at': datetime.now().isoformat(),
                'status': 'confirmed'
            }
            
            self.appointments.append(appointment)
            logger.info(f"Appointment booked: {appointment}")
            
            return appointment
        
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            raise
    
    def get_appointments(self) -> List[Dict]:
        """Get all appointments"""
        return self.appointments
    
    def get_appointment_by_id(self, appointment_id: str) -> Dict:
        """Get a specific appointment by ID"""
        for apt in self.appointments:
            if apt['id'] == appointment_id:
                return apt
        return None

# Singleton instance
appointment_service = AppointmentService()