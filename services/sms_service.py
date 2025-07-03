import boto3
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self, aws_access_key: Optional[str] = None, aws_secret_key: Optional[str] = None, aws_region: str = 'us-east-1'):
        """Initialize Amazon SNS client"""
        self.sns_client = None
        self.enabled = False
        
        # Safe debug print
        access_key_preview = aws_access_key[:4] + "..." if aws_access_key else "None"
        print(f"SMS Service Init - Access key: {access_key_preview} Secret key set: {bool(aws_secret_key)} Region: {aws_region}")
        
        try:
            if aws_access_key and aws_secret_key:
                print("Creating SNS client with provided credentials...")
                self.sns_client = boto3.client(
                    'sns',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
            else:
                print("Creating SNS client with default credentials...")
                self.sns_client = boto3.client('sns', region_name=aws_region)
            
            print("Testing SNS client connection...")
            # Test if credentials work
            response = self.sns_client.list_topics()
            print(f"SNS test successful: Found {len(response.get('Topics', []))} topics")
            
            logger.info("SMS service initialized with Amazon SNS")
            self.enabled = True
            
        except Exception as e:
            print(f"SMS service initialization failed: {e}")
            print(f"Error type: {type(e).__name__}")
            logger.warning(f"SMS service not available: {e}")
            self.sns_client = None
            self.enabled = False
    
    def send_monthly_summary(self, phone_number: str, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send monthly summary via SMS"""
        
        if not self.enabled or not self.sns_client:
            logger.warning("SMS service not enabled - skipping SMS")
            return {"success": False, "error": "SMS service not configured"}
        
        # Format phone number (ensure it starts with +)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Create SMS message
        message = self.format_monthly_sms(summary_data)
        
        try:
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    },
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': 'RAPIDODEV1'
                    }
                }
            )
            
            logger.info(f"Monthly SMS sent to {phone_number}: {response['MessageId']}")
            
            return {
                "success": True,
                "message_id": response['MessageId'],
                "phone_number": phone_number
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def format_monthly_sms(self, summary_data: Dict[str, Any]) -> str:
        """Format monthly summary for SMS"""
        
        month_name = summary_data['month_year']
        
        message = f"""📊 {month_name} Expense Summary

💰 Total: ₺{summary_data['tl_total']:.2f} → {summary_data['mwk_total']:.2f} MWK
🧾 {summary_data['transaction_count']} transactions

Top spending: {summary_data.get('top_merchant', 'N/A')}

Receipt Tracker Bot"""
        
        return message
    
    def send_test_sms(self, phone_number: str, message: str = "Test message from Receipt Tracker Bot! 🤖") -> Dict[str, Any]:
        """Send test SMS"""
        
        if not self.enabled or not self.sns_client:
            return {"success": False, "error": "SMS service not configured"}
        
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        try:
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    },
                    'AWS.SNS.SMS.SenderID': {  
                        'DataType': 'String',
                        'StringValue': 'RAPIDODEV1'
                    }
                }
            )
            
            return {
                "success": True,
                "message_id": response['MessageId']
            }
            
        except Exception as e:
            logger.error(f"Test SMS failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def is_available(self) -> bool:
        """Check if SMS service is available"""
        return self.enabled and self.sns_client is not None