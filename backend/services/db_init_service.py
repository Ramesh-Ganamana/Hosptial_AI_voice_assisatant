"""
Database Schema Initialization Service
Creates and populates collections for hospital appointment system
"""
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

async def initialize_database(db: AsyncIOMotorDatabase):
    """Initialize database with schema and sample data"""
    
    logger.info("Initializing hospital appointment database...")
    
    # Create indexes for performance
    await db.doctors.create_index("doctor_id", unique=True)
    await db.departments.create_index("department_id", unique=True)
    await db.appointments.create_index([("doctor_id", 1), ("appointment_date", 1), ("start_time", 1)])
    await db.doctor_absence.create_index([("doctor_id", 1), ("absent_date", 1)])
    await db.surgery_blocks.create_index([("doctor_id", 1), ("surgery_date", 1)])
    
    # Check if data already exists
    doctor_count = await db.doctors.count_documents({})
    if doctor_count > 0:
        logger.info(f"Database already initialized with {doctor_count} doctors")
        return
    
    # Insert departments
    departments = [
        {"department_id": "DEPT001", "department_name": "Cardiology"},
        {"department_id": "DEPT002", "department_name": "Neurology"},
        {"department_id": "DEPT003", "department_name": "Orthopedics"},
        {"department_id": "DEPT004", "department_name": "ENT"},
        {"department_id": "DEPT005", "department_name": "Pediatrics"},
        {"department_id": "DEPT006", "department_name": "Dermatology"},
        {"department_id": "DEPT007", "department_name": "Oncology"},
        {"department_id": "DEPT008", "department_name": "Gynecology"},
        {"department_id": "DEPT009", "department_name": "General Medicine"},
        {"department_id": "DEPT010", "department_name": "Surgery"}
    ]
    await db.departments.insert_many(departments)
    logger.info(f"Inserted {len(departments)} departments")
    
    # Insert doctors (multiple per department)
    doctors = [
        # Cardiology
        {"doctor_id": "DOC001", "doctor_name": "Dr. Rajesh Kumar", "department_id": "DEPT001", "specialization": "Interventional Cardiology", "active_status": True},
        {"doctor_id": "DOC002", "doctor_name": "Dr. Priya Sharma", "department_id": "DEPT001", "specialization": "Pediatric Cardiology", "active_status": True},
        {"doctor_id": "DOC003", "doctor_name": "Dr. Amit Verma", "department_id": "DEPT001", "specialization": "Cardiac Surgery", "active_status": True},
        
        # Neurology
        {"doctor_id": "DOC004", "doctor_name": "Dr. Sunita Reddy", "department_id": "DEPT002", "specialization": "Neurologist", "active_status": True},
        {"doctor_id": "DOC005", "doctor_name": "Dr. Vikram Singh", "department_id": "DEPT002", "specialization": "Neurosurgeon", "active_status": True},
        
        # Orthopedics
        {"doctor_id": "DOC006", "doctor_name": "Dr. Meera Iyer", "department_id": "DEPT003", "specialization": "Joint Replacement", "active_status": True},
        {"doctor_id": "DOC007", "doctor_name": "Dr. Arjun Patel", "department_id": "DEPT003", "specialization": "Sports Medicine", "active_status": True},
        {"doctor_id": "DOC008", "doctor_name": "Dr. Kavita Menon", "department_id": "DEPT003", "specialization": "Spine Surgery", "active_status": True},
        
        # ENT
        {"doctor_id": "DOC009", "doctor_name": "Dr. Ravi Gupta", "department_id": "DEPT004", "specialization": "ENT Specialist", "active_status": True},
        {"doctor_id": "DOC010", "doctor_name": "Dr. Anjali Desai", "department_id": "DEPT004", "specialization": "Head & Neck Surgery", "active_status": True},
        
        # Pediatrics
        {"doctor_id": "DOC011", "doctor_name": "Dr. Sanjay Nair", "department_id": "DEPT005", "specialization": "Pediatrician", "active_status": True},
        {"doctor_id": "DOC012", "doctor_name": "Dr. Deepa Krishnan", "department_id": "DEPT005", "specialization": "Neonatologist", "active_status": True},
        
        # Dermatology
        {"doctor_id": "DOC013", "doctor_name": "Dr. Ramesh Joshi", "department_id": "DEPT006", "specialization": "Dermatologist", "active_status": True},
        {"doctor_id": "DOC014", "doctor_name": "Dr. Pooja Malhotra", "department_id": "DEPT006", "specialization": "Cosmetic Dermatology", "active_status": True},
        
        # Oncology
        {"doctor_id": "DOC015", "doctor_name": "Dr. Suresh Rao", "department_id": "DEPT007", "specialization": "Medical Oncologist", "active_status": True},
        {"doctor_id": "DOC016", "doctor_name": "Dr. Nisha Kapoor", "department_id": "DEPT007", "specialization": "Radiation Oncologist", "active_status": True},
        
        # Gynecology
        {"doctor_id": "DOC017", "doctor_name": "Dr. Lakshmi Pillai", "department_id": "DEPT008", "specialization": "Obstetrician", "active_status": True},
        {"doctor_id": "DOC018", "doctor_name": "Dr. Madhavi Shetty", "department_id": "DEPT008", "specialization": "Gynecologist", "active_status": True},
        
        # General Medicine
        {"doctor_id": "DOC019", "doctor_name": "Dr. Anil Kumar", "department_id": "DEPT009", "specialization": "General Physician", "active_status": True},
        {"doctor_id": "DOC020", "doctor_name": "Dr. Rekha Menon", "department_id": "DEPT009", "specialization": "Internal Medicine", "active_status": True}
    ]
    await db.doctors.insert_many(doctors)
    logger.info(f"Inserted {len(doctors)} doctors")
    
    # Insert working hours for all doctors (Mon-Sat, 9 AM to 5 PM)
    working_hours = []
    for doctor in doctors:
        # Generate working hours for next 30 days
        for day_offset in range(30):
            date = (datetime.now() + timedelta(days=day_offset)).date()
            # Skip Sundays
            if date.weekday() != 6:
                working_hours.append({
                    "doctor_id": doctor["doctor_id"],
                    "working_date": date.isoformat(),
                    "start_time": "09:00",
                    "end_time": "17:00",
                    "total_hours": 8
                })
    
    await db.doctor_working_hours.insert_many(working_hours)
    logger.info(f"Inserted {len(working_hours)} working hour entries")
    
    logger.info("Database initialization complete!")


async def seed_sample_appointments(db: AsyncIOMotorDatabase):
    """Seed some sample appointments for testing"""
    
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    # Sample appointments
    appointments = [
        {
            "appointment_id": "APT001",
            "doctor_id": "DOC001",
            "patient_id": "PAT001",
            "patient_name": "John Doe",
            "appointment_date": today.isoformat(),
            "start_time": "10:00",
            "end_time": "10:15",
            "appointment_type": "Consultation",
            "status": "CONFIRMED"
        },
        {
            "appointment_id": "APT002",
            "doctor_id": "DOC001",
            "patient_id": "PAT002",
            "patient_name": "Jane Smith",
            "appointment_date": today.isoformat(),
            "start_time": "11:00",
            "end_time": "11:15",
            "appointment_type": "Follow-up",
            "status": "CONFIRMED"
        }
    ]
    
    await db.appointments.insert_many(appointments)
    logger.info(f"Seeded {len(appointments)} sample appointments")
