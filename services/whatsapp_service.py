import requests
import json
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self, access_token, phone_number_id):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v22.0/{phone_number_id}"
        
        logger.info(f"WhatsApp service initialized with phone ID: {phone_number_id}")
        
    def send_message(self, to_number, message_text):
        """Send a text message via WhatsApp"""
        url = f"{self.base_url}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Working format for text messages
        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {
                "body": message_text
            }
        }
        
        try:
            logger.info(f"Sending message to {to_number}: {message_text[:50]}...")
            response = requests.post(url, headers=headers, json=data)
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Message sent successfully to {to_number}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send message to {to_number}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response text: {e.response.text}")
            return None
    
    def send_template_message(self, to_number, template_name="hello_world", language_code="en_US"):
        """Send a template message (like hello_world)"""
        url = f"{self.base_url}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messaging_product": "whatsapp",  # Required for template messages
            "to": to_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }
        
        try:
            logger.info(f"Sending template message '{template_name}' to {to_number}")
            response = requests.post(url, headers=headers, json=data)
            
            logger.info(f"Template response status: {response.status_code}")
            logger.info(f"Template response body: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Template message sent successfully to {to_number}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send template message to {to_number}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response text: {e.response.text}")
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
            "messaging_product": "whatsapp",  # Required for interactive messages
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message_text},
                "action": {"buttons": button_data}
            }
        }
        
        try:
            logger.info(f"Sending interactive message to {to_number}")
            response = requests.post(url, headers=headers, json=data)
            
            logger.info(f"Interactive response status: {response.status_code}")
            logger.info(f"Interactive response body: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Interactive message sent successfully to {to_number}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send interactive message to {to_number}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response text: {e.response.text}")
            return None
    
    def download_media(self, media_id):
        """Download media file (images) from WhatsApp"""
        # Get media URL
        url = f"https://graph.facebook.com/v22.0/{media_id}"
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