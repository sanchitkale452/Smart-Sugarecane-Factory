"""
Gemini AI Service for Chatbot Integration
Handles all interactions with Google's Gemini API
"""
import os
from google import genai
from django.conf import settings
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class GeminiChatbotService:
    """Service class to handle Gemini AI chatbot interactions."""
    
    def __init__(self):
        """Initialize the Gemini service with API key and model."""
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")
        
        # Configure Gemini Client
        self.client = genai.Client(api_key=self.api_key)
        
        # Initialize the model configs
        self.config = {}
        
        # Initialize chat session
        self.chat = None
        
        logger.info(f"Gemini service initialized with model: {self.model_name}")
    
    def get_system_context(self, user) -> str:
        """
        Generate system context with factory data for better responses.
        
        Args:
            user: The Django user object
            
        Returns:
            str: System context string
        """
        try:
            from inventory.models import Item, InventoryTransaction
            from farms.models import Farm
            from production.models import ProductionBatch
            
            # Gather factory statistics
            total_items = Item.objects.filter(is_active=True).count()
            total_farms = Farm.objects.count()
            active_farms = Farm.objects.filter(status='active').count()
            active_batches = ProductionBatch.objects.filter(
                status__in=['pending', 'in_progress']
            ).count()
            completed_batches = ProductionBatch.objects.filter(
                status='completed'
            ).count()
            
            context = f"""You are a helpful AI assistant for a Sugarcane Factory Management System.
You are helping {user.get_full_name() or user.username}.

Current Factory Status:
- Total Inventory Items: {total_items}
- Total Farms: {total_farms} ({active_farms} active)
- Active Production Batches: {active_batches}
- Completed Production Batches: {completed_batches}

Your role is to:
1. Answer questions about inventory, production, and farm management
2. Provide helpful guidance on using the system
3. Give insights based on the current factory data
4. Be concise and professional
5. If you don't have specific data, provide general helpful information

Always be friendly, professional, and helpful. Keep responses concise and actionable."""
            
            return context
            
        except Exception as e:
            logger.error(f"Error generating system context: {e}")
            return """You are a helpful AI assistant for a Sugarcane Factory Management System.
Help users with inventory, production, and farm management questions."""
    
    def start_chat(self, user) -> None:
        """
        Start a new chat session with system context.
        
        Args:
            user: The Django user object
        """
        try:
            system_context = self.get_system_context(user)
            
            # Start chat with system instruction
            self.chat = self.client.chats.create(
                model=self.model_name,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_context
                )
            )
            
            logger.info(f"Chat session started for user: {user.username}")
            
        except Exception as e:
            logger.error(f"Error starting chat session: {e}")
            raise
    
    def send_message(self, user_message: str, user) -> Dict[str, Any]:
        """
        Send a message to Gemini and get response.
        
        Args:
            user_message: The user's message
            user: The Django user object
            
        Returns:
            dict: Response containing text and optional data
        """
        try:
            # Start chat if not already started
            if not self.chat:
                self.start_chat(user)
            
            # Send message and get response
            response = self.chat.send_message(user_message)
            
            result = {
                'text': response.text,
                'data': None,
                'success': True
            }
            
            logger.info(f"Message sent successfully for user: {user.username}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending message to Gemini: {e}")
            return {
                'text': "I apologize, but I'm having trouble processing your request right now. Please try again.",
                'data': None,
                'success': False,
                'error': str(e)
            }
    
    def get_contextual_response(self, query: str, user, context_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get a contextual response with additional data.
        
        Args:
            query: User's query
            user: Django user object
            context_data: Optional additional context data
            
        Returns:
            dict: Response with text and data
        """
        try:
            # Add context data to query if provided
            enhanced_query = query
            if context_data:
                context_str = "\n\nAdditional Context:\n"
                for key, value in context_data.items():
                    context_str += f"- {key}: {value}\n"
                enhanced_query = query + context_str
            
            return self.send_message(enhanced_query, user)
            
        except Exception as e:
            logger.error(f"Error getting contextual response: {e}")
            return {
                'text': "I'm having trouble understanding your request. Could you please rephrase?",
                'data': None,
                'success': False,
                'error': str(e)
            }
    
    def reset_chat(self) -> None:
        """Reset the chat session."""
        self.chat = None
        logger.info("Chat session reset")


# Singleton instance
_gemini_service = None


def get_gemini_service() -> GeminiChatbotService:
    """
    Get or create the Gemini service singleton.
    
    Returns:
        GeminiChatbotService: The service instance
    """
    global _gemini_service
    
    if _gemini_service is None:
        try:
            _gemini_service = GeminiChatbotService()
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            raise
    
    return _gemini_service
