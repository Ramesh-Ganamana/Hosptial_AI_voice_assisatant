import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class DoctorService:
    def __init__(self):
        # Load doctors data
        data_path = Path(__file__).parent.parent / "data" / "doctors.json"
        logger.info(f"Loading doctors data from {data_path}")
        
        with open(data_path, 'r') as f:
            self.doctors = json.load(f)
        
        logger.info(f"Loaded {len(self.doctors)} doctors")
    
    def get_all_doctors(self) -> List[Dict]:
        """Get all doctors"""
        return self.doctors
    
    def get_doctors_by_specialty(self, specialty: str) -> List[Dict]:
        """Get doctors by specialty"""
        specialty_lower = specialty.lower()
        return [
            doc for doc in self.doctors 
            if specialty_lower in doc['specialty'].lower()
        ]
    
    def get_doctor_by_id(self, doctor_id: str) -> Optional[Dict]:
        """Get a specific doctor by ID"""
        for doc in self.doctors:
            if doc['id'] == doctor_id:
                return doc
        return None
    
    def get_doctor_by_name(self, name: str) -> Optional[Dict]:
        """Get a doctor by name (case-insensitive partial match)"""
        name_lower = name.lower()
        for doc in self.doctors:
            if name_lower in doc['name'].lower():
                return doc
        return None
    
    def format_doctor_info(self, doctor: Dict) -> str:
        """Format doctor information as a readable string"""
        info = f"{doctor['name']} - {doctor['specialty']}\n"
        info += f"Available Days: {', '.join(doctor['available_days'])}\n"
        info += f"Available Times: {', '.join(doctor['available_times'])}"
        return info

# Singleton instance
doctor_service = DoctorService()