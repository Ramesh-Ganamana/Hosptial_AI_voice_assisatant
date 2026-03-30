"""
Slot Generation Service
Generates 15-minute time slots dynamically based on doctor working hours
"""
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

class SlotGenerationService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.slot_duration_minutes = 15  # Each consultation is 15 minutes
    
    def generate_time_slots(self, start_time: str, end_time: str) -> List[str]:
        """
        Generate 15-minute slots between start and end time
        
        Args:
            start_time: Start time in HH:MM format (e.g., "09:00")
            end_time: End time in HH:MM format (e.g., "17:00")
        
        Returns:
            List of time slots in HH:MM format
        """
        slots = []
        
        # Parse times
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        
        # Create datetime objects for easier manipulation
        start_dt = datetime.combine(datetime.today(), time(start_hour, start_minute))
        end_dt = datetime.combine(datetime.today(), time(end_hour, end_minute))
        
        # Generate slots
        current_time = start_dt
        while current_time < end_dt:
            slots.append(current_time.strftime("%H:%M"))
            current_time += timedelta(minutes=self.slot_duration_minutes)
        
        return slots
    
    async def get_available_slots(
        self,
        doctor_id: str,
        appointment_date: str
    ) -> Dict:
        """
        Get all available slots for a doctor on a specific date
        
        Args:
            doctor_id: Doctor ID
            appointment_date: Date in YYYY-MM-DD format
        
        Returns:
            Dict with available slots and blocked reasons
        """
        result = {
            "doctor_id": doctor_id,
            "date": appointment_date,
            "available_slots": [],
            "blocked_slots": {},
            "total_slots": 0
        }
        
        # 1. Check if doctor is absent
        absence = await self.db.doctor_absence.find_one({
            "doctor_id": doctor_id,
            "absent_date": appointment_date,
            "status": "ABSENT"
        })
        
        if absence:
            result["doctor_absent"] = True
            result["absence_reason"] = absence.get("reason", "Not available")
            return result
        
        # 2. Get doctor working hours for this date
        working_hours = await self.db.doctor_working_hours.find_one({
            "doctor_id": doctor_id,
            "working_date": appointment_date
        })
        
        if not working_hours:
            result["no_working_hours"] = True
            return result
        
        # 3. Generate all possible slots
        all_slots = self.generate_time_slots(
            working_hours["start_time"],
            working_hours["end_time"]
        )
        result["total_slots"] = len(all_slots)
        
        # 4. Get all existing appointments
        appointments = await self.db.appointments.find({
            "doctor_id": doctor_id,
            "appointment_date": appointment_date,
            "status": {"$in": ["CONFIRMED", "PENDING"]}
        }).to_list(length=None)
        
        booked_slots = set()
        for apt in appointments:
            booked_slots.add(apt["start_time"])
            result["blocked_slots"][apt["start_time"]] = "Already booked"
        
        # 5. Get surgery blocks
        surgeries = await self.db.surgery_blocks.find({
            "doctor_id": doctor_id,
            "surgery_date": appointment_date,
            "status": "SURGERY_BLOCK"
        }).to_list(length=None)
        
        surgery_slots = set()
        for surgery in surgeries:
            blocked = self._get_slots_in_range(
                surgery["surgery_start_time"],
                surgery["surgery_end_time"],
                all_slots
            )
            surgery_slots.update(blocked)
            for slot in blocked:
                result["blocked_slots"][slot] = "Surgery scheduled"
        
        # 6. Get manual blocked slots
        blocked = await self.db.manual_blocked_slots.find({
            "doctor_id": doctor_id,
            "blocked_date": appointment_date
        }).to_list(length=None)
        
        manual_slots = set()
        for block in blocked:
            blocked_range = self._get_slots_in_range(
                block["blocked_start_time"],
                block["blocked_end_time"],
                all_slots
            )
            manual_slots.update(blocked_range)
            for slot in blocked_range:
                result["blocked_slots"][slot] = block.get("reason", "Blocked")
        
        # 7. Calculate available slots
        unavailable = booked_slots | surgery_slots | manual_slots
        result["available_slots"] = [
            slot for slot in all_slots 
            if slot not in unavailable
        ]
        
        return result
    
    def _get_slots_in_range(
        self,
        start_time: str,
        end_time: str,
        all_slots: List[str]
    ) -> List[str]:
        """Get all slots that fall within a time range"""
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        
        start_dt = datetime.combine(datetime.today(), time(start_hour, start_minute))
        end_dt = datetime.combine(datetime.today(), time(end_hour, end_minute))
        
        blocked_slots = []
        for slot in all_slots:
            slot_hour, slot_minute = map(int, slot.split(':'))
            slot_dt = datetime.combine(datetime.today(), time(slot_hour, slot_minute))
            
            # Check if slot falls within the range
            if start_dt <= slot_dt < end_dt:
                blocked_slots.append(slot)
        
        return blocked_slots
    
    async def is_slot_available(
        self,
        doctor_id: str,
        appointment_date: str,
        start_time: str
    ) -> Dict:
        """
        Check if a specific slot is available
        
        Returns:
            Dict with availability status and reason if not available
        """
        # Get all available slots
        slots_data = await self.get_available_slots(doctor_id, appointment_date)
        
        if slots_data.get("doctor_absent"):
            return {
                "available": False,
                "reason": f"Doctor is unavailable: {slots_data.get('absence_reason')}"
            }
        
        if slots_data.get("no_working_hours"):
            return {
                "available": False,
                "reason": "Doctor is not working on this date"
            }
        
        if start_time in slots_data["available_slots"]:
            return {
                "available": True,
                "slot": start_time
            }
        
        # Find the reason why slot is not available
        reason = slots_data["blocked_slots"].get(
            start_time,
            "Time slot not in working hours"
        )
        
        return {
            "available": False,
            "reason": reason,
            "next_available": slots_data["available_slots"][:5] if slots_data["available_slots"] else []
        }
