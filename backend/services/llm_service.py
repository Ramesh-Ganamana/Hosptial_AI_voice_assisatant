import logging
import os
from typing import List, Dict
from emergentintegrations.llm.chat import LlmChat, UserMessage
from dotenv import load_dotenv
from .doctor_service import doctor_service

load_dotenv()
logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
        
        # Store active chat sessions
        self.sessions: Dict[str, LlmChat] = {}
        
        logger.info("LLM Service initialized")
    
    def get_or_create_session(self, session_id: str) -> LlmChat:
        """Get existing chat session or create a new one"""
        if session_id not in self.sessions:
            # Get doctors data for context
            doctors = doctor_service.get_all_doctors()
            doctors_info = "\n".join([
                f"- {doc['name']}: {doc['specialty']} (Available: {', '.join(doc['available_days'])})"
                for doc in doctors
            ])
            
            system_message = f"""You are a helpful AI assistant for a hospital. You help patients:
1. Find available doctors by specialty
2. Check doctor availability
3. Book appointments

Available Doctors:
{doctors_info}

When users ask about doctors:
- List specific doctor names, their specialties, and availability
- Be conversational and helpful
- If they want to book an appointment, ask for: patient name, preferred date, and time
- Understand Indian English accents and context

Be natural, friendly, and professional."""
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=system_message
            )
            # Use GPT-4o model
            chat.with_model("openai", "gpt-4o")
            self.sessions[session_id] = chat
            logger.info(f"Created new chat session: {session_id}")
        
        return self.sessions[session_id]
    
    async def process_message(self, session_id: str, user_text: str) -> str:
        """Process user message and return AI response"""
        try:
            chat = self.get_or_create_session(session_id)
            user_message = UserMessage(text=user_text)
            
            logger.info(f"Processing message for session {session_id}: {user_text}")
            response = await chat.send_message(user_message)
            
            logger.info(f"LLM response: {response}")
            return response
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again."
    
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

# Singleton instance
llm_service = LLMService()
