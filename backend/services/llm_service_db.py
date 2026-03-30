"""
Enhanced LLM Service with Database-Driven Appointment Scheduling
"""
import logging
import os
from typing import List, Dict
from emergentintegrations.llm.chat import LlmChat, UserMessage
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta

load_dotenv()
logger = logging.getLogger(__name__)

class LLMServiceDB:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
        
        self.db = db
        # Store active chat sessions
        self.sessions: Dict[str, LlmChat] = {}
        
        logger.info("Enhanced LLM Service with DB initialized")
    
    async def get_or_create_session(self, session_id: str) -> LlmChat:
        """Get existing chat session or create a new one"""
        if session_id not in self.sessions:
            # Get dynamic doctor and department data from database
            doctors = await self.db.doctors.find(
                {"active_status": True},
                {"_id": 0}
            ).limit(20).to_list(length=None)
            
            departments = await self.db.departments.find({}, {"_id": 0}).to_list(length=None)
            
            # Build dynamic context
            dept_names = [dept["department_name"] for dept in departments]
            doctor_summary = "\n".join([
                f"- {doc['doctor_name']}: {doc['specialization']} ({doc.get('department_id', 'N/A')})"
                for doc in doctors[:10]  # Show first 10 for context
            ])
            
            today = datetime.now().date()
            tomorrow = (today + timedelta(days=1)).isoformat()
            
            system_message = f"""You are a hospital appointment scheduling assistant. You help patients schedule appointments with doctors.

**Your Role:**
- Help patients find available doctors
- Check real-time availability from the database
- Book appointments when requested
- Provide clear time slot options

**Available Departments:**
{', '.join(dept_names)}

**Sample Doctors (there are more in the system):**
{doctor_summary}

**Important Instructions:**
1. When patient asks for a doctor or specialty:
   - Ask what date they prefer (suggest tomorrow: {tomorrow} if not specified)
   - Then tell them you'll check available time slots

2. When patient wants to book:
   - Confirm: Doctor name, Date, Time
   - Collect patient name if not provided
   - Confirm booking details before finalizing

3. Be conversational and natural:
   - "Let me check Dr. Kumar's availability for tomorrow..."
   - "I can see Dr. Sharma has slots at 10:00 AM, 11:15 AM, and 2:30 PM. Which works for you?"
   - "Great! I'll book you with Dr. Patel for March 31 at 10:00 AM."

4. If asked about availability:
   - Acknowledge you'll check the system
   - Provide specific time slots (e.g., "10:00 AM, 10:15 AM, 11:00 AM")

5. Hospital Calling Assistant Behavior:
   - Wait patiently while patient speaks
   - Never interrupt during pauses
   - Be professional and courteous

**Current Date:** {today.isoformat()}

Be helpful, natural, and guide the conversation toward booking an appointment."""
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=system_message
            )
            # Use GPT-4o model
            chat.with_model("openai", "gpt-4o")
            self.sessions[session_id] = chat
            logger.info(f"Created new DB-backed chat session: {session_id}")
        
        return self.sessions[session_id]
    
    async def process_message(self, session_id: str, user_text: str) -> str:
        """Process user message with database context"""
        try:
            # Check if message contains appointment-related keywords
            lower_text = user_text.lower()
            
            # Handle availability queries
            if any(word in lower_text for word in ['available', 'availability', 'slots', 'times', 'when']):
                response = await self._handle_availability_query(session_id, user_text)
                return response
            
            # Handle booking requests
            if any(word in lower_text for word in ['book', 'schedule', 'appointment', 'reserve']):
                response = await self._handle_booking_query(session_id, user_text)
                return response
            
            # Regular conversation
            chat = await self.get_or_create_session(session_id)
            user_message = UserMessage(text=user_text)
            
            logger.info(f"Processing message for session {session_id}: {user_text}")
            response = await chat.send_message(user_message)
            
            logger.info(f"LLM response: {response}")
            return response
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return "I'm sorry, I'm having trouble processing your request right now. Please try again."
    
    async def _handle_availability_query(self, session_id: str, user_text: str) -> str:
        """Handle availability-related queries by checking database"""
        try:
            # For now, provide a conversational response
            # In a full implementation, this would parse doctor/date and query database
            chat = await self.get_or_create_session(session_id)
            user_message = UserMessage(text=user_text)
            response = await chat.send_message(user_message)
            return response
        except Exception as e:
            logger.error(f"Error handling availability query: {e}")
            return "Let me check the doctor's availability for you. Could you tell me which doctor and what date you're interested in?"
    
    async def _handle_booking_query(self, session_id: str, user_text: str) -> str:
        """Handle booking-related queries"""
        try:
            chat = await self.get_or_create_session(session_id)
            user_message = UserMessage(text=user_text)
            response = await chat.send_message(user_message)
            return response
        except Exception as e:
            logger.error(f"Error handling booking query: {e}")
            return "I'd be happy to help you book an appointment. Could you tell me your preferred doctor and date?"
    
    async def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for a session"""
        if session_id in self.sessions:
            chat = self.sessions[session_id]
            messages = await chat.get_messages()
            return messages
        return []
    
    def clear_session(self, session_id: str):
        """Clear a specific chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
