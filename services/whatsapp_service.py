import requests
import json
import logging
from config import Config

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self, access_token, phone_number_id):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v18.0/{phone_number_id}"
        
    def send_message(self, to_number, message_text):
        """Send a text message"""
        url = f"{self.base_url}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message_text}
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Message sent to {to_number}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def send_interactive_message(self, to_number, message_text, buttons):
        """Send message with interactive buttons"""
        url = f"{self.base_url}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Format buttons for WhatsApp API
        button_data = []
        for i, button in enumerate(buttons):
            button_data.append({
                "type": "reply",
                "reply": {
                    "id": button['id'],
                    "title": button['title']
                }
            })
        
        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message_text},
                "action": {"buttons": button_data}
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Interactive message sent to {to_number}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send interactive message: {e}")
            return None
    
    def download_media(self, media_id):
        """Download media file (images) from WhatsApp"""
        # Get media URL
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            # Get media info
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            media_info = response.json()
            
            # Download the actual file
            media_url = media_info.get('url')
            if media_url:
                media_response = requests.get(media_url, headers=headers)
                media_response.raise_for_status()
                return media_response.content
            
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download media: {e}")
            return None
    
    def mark_as_read(self, message_id):
        """Mark message as read"""
        url = f"{self.base_url}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to mark as read: {e}")
            return False