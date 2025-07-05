import logging
import json
from datetime import datetime
from services.database_service import DatabaseService
from models import db, Expense  # Added missing imports
from sqlalchemy import func, distinct  # Added missing imports

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, whatsapp_service, ocr_service=None, llm_service=None, exchange_rate_service=None, monthly_tracking=None):
        self.whatsapp = whatsapp_service
        self.ocr_service = ocr_service
        self.llm_service = llm_service
        self.exchange_rate_service = exchange_rate_service
        self.monthly_tracking = monthly_tracking
        
        # Store pending receipts for rate selection
        self.pending_receipts = {}
        
        # Store pending manual entries for rate selection
        self.pending_manual_entries = {}
        
        # Store manual entry states (amount -> merchant -> rate)
        self.manual_entry_states = {}
        
        logger.info("Message handler initialized with services")
    
    def handle_incoming_message(self, webhook_data):
        """Process incoming WhatsApp messages"""
        try:
            # Extract message data from webhook
            entry = webhook_data.get('entry', [])
            if not entry:
                logger.warning("No entry in webhook data")
                return
                
            changes = entry[0].get('changes', [])
            if not changes:
                logger.warning("No changes in webhook entry")
                return
                
            value = changes[0].get('value', {})
            messages = value.get('messages', [])
            
            for message in messages:
                self.process_message(message)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def process_message(self, message):
        """Process individual message"""
        try:
            message_type = message.get('type')
            from_number = message.get('from')
            message_id = message.get('id')
            
            logger.info(f"Processing {message_type} message from {from_number}")
            
            # Try to mark as read, but don't fail if it doesn't work
            try:
                self.whatsapp.mark_as_read(message_id)
            except Exception as read_error:
                logger.warning(f"Failed to mark message as read (continuing anyway): {read_error}")
            
            # Get or create user
            user = DatabaseService.get_or_create_user(from_number)
            
            if message_type == 'text':
                self.handle_text_message(message, from_number, user)
            elif message_type == 'image':
                self.handle_image_message(message, from_number, user)
            elif message_type == 'interactive':
                self.handle_interactive_message(message, from_number, user)
            else:
                logger.info(f"Unsupported message type: {message_type}")
                self.send_help_message(from_number)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Continue processing other messages even if one fails

    def handle_text_message(self, message, from_number, user):
        """Handle text messages"""
        text = message.get('text', {}).get('body', '').lower().strip()
        
        logger.info(f"Processing text: '{text}' from {from_number}")
        
        if text in ['hi', 'hello', 'hey', 'start']:
            self.send_welcome_message(from_number)
        elif text in ['help', 'info']:
            self.send_help_message(from_number)
        elif text in ['total', 'balance', 'summary', 'totals']:
            self.send_month_picker(from_number, user.id)
        elif text in ['manual', 'entry', 'add', 'lost receipt', 'no receipt']:
            self.start_manual_entry(from_number)
        elif text in ['details', 'items', 'breakdown', 'list']:
            self.send_recent_items_breakdown(from_number, user.id)
        elif text.upper() in ['POS', 'ATM']:
            self.handle_rate_selection(from_number, user, text.upper())
        elif self.is_amount_entry(text):
            self.handle_manual_amount(from_number, user, text)
        elif from_number in self.manual_entry_states and self.manual_entry_states[from_number].get('awaiting_merchant'):
            self.handle_manual_merchant(from_number, user, text)
        else:
            self.send_help_message(from_number)

    def send_month_picker(self, to_number, user_id):
        """Send month picker with available months and all-time option"""
        try:
            # Get all months that have expenses for this user
            months_with_expenses = db.session.query(
                distinct(Expense.month_year)
            ).filter(
                Expense.user_id == user_id
            ).order_by(
                Expense.month_year.desc()
            ).all()
            
            if not months_with_expenses:
                self.whatsapp.send_message(
                    to_number,
                    "📊 *No Expenses Found*\n\nYou haven't recorded any expenses yet!\n\nSend a receipt image or use 'manual' to add an expense."
                )
                return
            
            # Create month list message
            available_months = [month[0] for month in months_with_expenses]
            
            message = "📊 *Choose Month to View*\n\nSelect which month you'd like to see:"
            
            # Create buttons for months + all time
            buttons = []
            
            # Add up to 2 most recent months as buttons (WhatsApp limit is 3 buttons)
            for i, month_year in enumerate(available_months[:2]):
                month_name = self.format_month_name(month_year)
                buttons.append({
                    "id": f"month_{month_year}",
                    "title": f"📅 {month_name}"
                })
            
            # Always add "All Time" button
            buttons.append({
                "id": "all_time", 
                "title": "📊 All Time"
            })
            
            # If there are more than 2 months, mention them in the message
            if len(available_months) > 2:
                other_months = available_months[2:]
                message += f"\n\n*Other available months:*"
                for month_year in other_months:
                    month_name = self.format_month_name(month_year)
                    message += f"\n• {month_name}"
                message += f"\n\nType the month name (e.g., 'June 2025') to view older months."
            
            # Send interactive message with buttons
            self.whatsapp.send_interactive_message(
                to_number,
                message,
                buttons
            )
            
        except Exception as e:
            logger.error(f"Error sending month picker: {e}")
            self.whatsapp.send_message(
                to_number,
                "❌ Error loading expense months. Please try again."
            )

    def format_month_name(self, month_year):
        """Convert '2025-07' to 'July 2025'"""
        try:
            from datetime import datetime
            date_obj = datetime.strptime(month_year, '%Y-%m')
            return date_obj.strftime('%B %Y')
        except:
            return month_year

    def handle_interactive_message(self, message, from_number, user):
        """Handle button clicks"""
        try:
            button_reply = message.get('interactive', {}).get('button_reply', {})
            button_id = button_reply.get('id')
            
            logger.info(f"Button clicked: {button_id} by {from_number}")
            
            if button_id == 'pos_rate':
                self.handle_rate_selection(from_number, user, 'POS')
            elif button_id == 'atm_rate':
                self.handle_rate_selection(from_number, user, 'ATM')
            elif button_id == 'all_time':
                self.send_all_time_total(from_number, user.id)
            elif button_id.startswith('month_'):
                month_year = button_id.replace('month_', '')
                self.send_specific_month_total(from_number, user.id, month_year)
            else:
                self.send_help_message(from_number)
                
        except Exception as e:
            logger.error(f"Error handling interactive message: {e}")

    def send_specific_month_total(self, to_number, user_id, month_year):
        """Send total for a specific month"""
        try:
            totals = DatabaseService.get_monthly_total(user_id, month_year)
            month_name = self.format_month_name(month_year)
            
            if totals['transaction_count'] == 0:
                message = f"""📊 *{month_name}*

No transactions found for {month_name}.

Use 'total' to see available months."""
            else:
                # Get expenses for this month to show breakdown
                expenses = Expense.query.filter(
                    Expense.user_id == user_id,
                    Expense.month_year == month_year
                ).order_by(Expense.expense_date.desc()).all()
                
                message = f"""📊 *{month_name}*

💰 *₺{totals['tl_total']:.2f}* → *{totals['mwk_total']:.2f} MWK*
🧾 *{totals['transaction_count']} transactions*

*Recent transactions:*"""
                
                # Show up to 5 most recent transactions with DD/MM format
                for expense in expenses[:5]:
                    # CHANGED: Use DD/MM format instead of MM/DD
                    date_str = expense.expense_date.strftime('%d/%m') if expense.expense_date else '??'
                    items = expense.get_items()
                    items_note = f" ({len(items)} items)" if items else ""
                    message += f"\n• {date_str} - {expense.merchant}: ₺{expense.amount_tl:.2f}{items_note}"
                
                if len(expenses) > 5:
                    message += f"\n... and {len(expenses) - 5} more"
                
                message += f"\n\n💡 Send 'details' to see item breakdowns"

            self.whatsapp.send_message(to_number, message)
            
        except Exception as e:
            logger.error(f"Error sending specific month total: {e}")
            self.whatsapp.send_message(
                to_number,
                f"❌ Error retrieving {month_year} data. Please try again."
            )

    def send_all_time_total(self, to_number, user_id):
        """Send all-time total across all months"""
        try:
            all_expenses = Expense.query.filter_by(user_id=user_id).order_by(
                Expense.expense_date.desc()
            ).all()
            
            if not all_expenses:
                message = """📊 *All-Time Total*

No transactions found.

Send a receipt image or use 'manual' to add your first expense!"""
            else:
                total_tl = sum(e.amount_tl for e in all_expenses)
                total_mwk = sum(e.amount_mwk for e in all_expenses)
                
                # Get date range with DD/MM/YYYY format
                oldest = min(e.expense_date for e in all_expenses if e.expense_date)
                newest = max(e.expense_date for e in all_expenses if e.expense_date)
                
                # Count total items
                total_items = sum(len(e.get_items()) for e in all_expenses)
                
                # CHANGED: Use DD/MM/YYYY format
                oldest_str = oldest.strftime('%d/%m/%Y') if oldest else '??'
                newest_str = newest.strftime('%d/%m/%Y') if newest else '??'
                
                message = f"""📊 *All-Time Total*

💰 *₺{total_tl:.2f}* → *{total_mwk:.2f} MWK*
🧾 *{len(all_expenses)} transactions*
🛍️ *{total_items} items tracked*
📅 *{oldest_str} - {newest_str}*

*Recent transactions:*"""
                
                # Show 5 most recent with DD/MM format
                for expense in all_expenses[:5]:
                    # CHANGED: Use DD/MM format
                    date_str = expense.expense_date.strftime('%d/%m') if expense.expense_date else '??'
                    items = expense.get_items()
                    items_note = f" ({len(items)} items)" if items else ""
                    message += f"\n• {date_str} - {expense.merchant}: ₺{expense.amount_tl:.2f}{items_note}"
                
                if len(all_expenses) > 5:
                    message += f"\n... and {len(all_expenses) - 5} more"
                
                message += f"\n\n💡 Send 'details' to see item breakdowns"

            self.whatsapp.send_message(to_number, message)
            
        except Exception as e:
            logger.error(f"Error sending all-time total: {e}")
            self.whatsapp.send_message(
                to_number,
                "❌ Error retrieving all-time data. Please try again."
            )

    def send_recent_items_breakdown(self, to_number, user_id):
        """Show detailed breakdown of recent purchases with items"""
        try:
            # Get last 5 expenses that have items
            recent_expenses = Expense.query.filter(
                Expense.user_id == user_id,
                Expense.items_json.isnot(None) # type: ignore
            ).order_by(Expense.expense_date.desc()).limit(5).all()
            
            if not recent_expenses:
                message = """📋 *Recent Items*

No detailed item information available yet.

💡 *Tip:* Send clearer receipt photos to capture individual item details!

📸 Try taking photos of itemized receipts from:
• Grocery stores (Migros, A101, etc.)
• Restaurants with itemized bills
• Shopping centers

Send 'total' for expense summaries"""
            else:
                message = "📋 *Recent Purchases - Item Breakdown*\n"
                
                for i, expense in enumerate(recent_expenses, 1):
                    items = expense.get_items()
                    # CHANGED: Use DD/MM format
                    date_str = expense.expense_date.strftime('%d/%m') if expense.expense_date else '??'
                    
                    message += f"\n**{i}. {expense.merchant}** ({date_str})"
                    message += f"\n💰 Total: ₺{expense.amount_tl:.2f} → {expense.amount_mwk:.2f} MWK"
                    
                    if items and len(items) > 0:
                        message += f"\n🛍️ Items ({len(items)}):"
                        for item in items:
                            name = item.get('name', 'Unknown')
                            price = item.get('price', 0)
                            qty = item.get('quantity', 1)
                            if qty > 1:
                                message += f"\n   • {name} x{qty} - ₺{price:.2f}"
                            else:
                                message += f"\n   • {name} - ₺{price:.2f}"
                    else:
                        message += f"\n   📦 (No item details captured)"
                    
                    message += "\n"
                
                message += "\n💡 Send 'total' for monthly summaries"
            
            self.whatsapp.send_message(to_number, message)
            
        except Exception as e:
            logger.error(f"Error sending items breakdown: {e}")
            self.whatsapp.send_message(
                to_number,
                "❌ Error retrieving item details. Please try again."
            )

    def handle_image_message(self, message, from_number, user):
        """Handle receipt images"""
        try:
            media_id = message.get('image', {}).get('id')
            
            if not media_id:
                self.whatsapp.send_message(
                    from_number,
                    "❌ Could not receive image. Please try again."
                )
                return
            
            # Send processing message
            self.whatsapp.send_message(
                from_number,
                "📄 Receipt received! Processing... ⏳"
            )
            
            # Check if services are available
            if not self.ocr_service or not self.llm_service:
                self.whatsapp.send_message(
                    from_number,
                    "❌ Receipt processing service not available. Please try again later."
                )
                return
            
            # Download image
            image_data = self.whatsapp.download_media(media_id)
            if not image_data:
                self.whatsapp.send_message(
                    from_number,
                    "❌ Could not download image. Please try again."
                )
                return
            
            # Process receipt
            self.process_receipt_image(from_number, user, image_data)
            
        except Exception as e:
            logger.error(f"Error handling image: {e}")
            self.whatsapp.send_message(
                from_number,
                f"❌ Error processing image: {str(e)}"
            )
    
    def process_receipt_image(self, from_number, user, image_data):
        """Process receipt image with OCR + LLM"""
        try:
            # Step 1: OCR
            ocr_result = self.ocr_service.extract_text_from_image(image_data) # type: ignore
            
            if not ocr_result['success']:
                self.whatsapp.send_message(
                    from_number,
                    f"❌ Could not read text from image: {ocr_result['error']}"
                )
                return
            
            # Step 2: LLM Processing
            llm_result = self.llm_service.process_receipt_text(ocr_result['text']) # type: ignore
            
            if not llm_result['success']:
                self.whatsapp.send_message(
                    from_number,
                    f"❌ Could not process receipt: {llm_result['error']}"
                )
                return
            
            # Step 3: Show rate selection
            extracted_data = llm_result['data']
            rate_selection = self.exchange_rate_service.create_rate_selection_message(extracted_data) # type: ignore # type: ignore
            
            # Store pending receipt
            self.pending_receipts[from_number] = extracted_data
            
            # Enhanced rate selection message with items preview
            items = extracted_data.get('items', [])
            items_preview = ""
            if items and len(items) > 0:
                items_preview = f"\n\n🛍️ *Items detected ({len(items)}):*"
                for item in items[:3]:  # Show first 3 items
                    name = item.get('name', 'Unknown')
                    price = item.get('price', 0)
                    items_preview += f"\n   • {name} - ₺{price:.2f}"
                if len(items) > 3:
                    items_preview += f"\n   • ... and {len(items) - 3} more"
            
            enhanced_message = rate_selection['message'] + items_preview
            
            # Send rate selection message
            self.whatsapp.send_message(from_number, enhanced_message)
            
            # Send rate selection buttons
            self.whatsapp.send_interactive_message(
                from_number,
                "Choose your rate:",
                [
                    {"id": "pos_rate", "title": "🏪 POS Rate"},
                    {"id": "atm_rate", "title": "🏧 ATM Rate"}
                ]
            )
            
        except Exception as e:
            logger.error(f"Receipt processing error: {e}")
            self.whatsapp.send_message(
                from_number,
                f"❌ Receipt processing failed: {str(e)}"
            )
    
    def handle_rate_selection(self, from_number, user, rate_type):
        """Handle rate selection and save receipt or manual entry"""
        try:
            extracted_data = None
            is_manual_entry = False
            
            # Check if we have pending receipt
            if from_number in self.pending_receipts:
                extracted_data = self.pending_receipts[from_number]
                is_manual_entry = False
            elif from_number in self.pending_manual_entries:
                extracted_data = self.pending_manual_entries[from_number]
                is_manual_entry = True
            else:
                self.whatsapp.send_message(
                    from_number,
                    "❌ No pending transaction found. Please send a receipt image or use 'manual' for manual entry."
                )
                return
            
            # Calculate conversion
            conversion = self.exchange_rate_service.calculate_conversion( # type: ignore
                extracted_data['total_amount'], 
                rate_type
            )
            
            # Prepare expense data
            expense_date = datetime.strptime(extracted_data['date'], '%Y-%m-%d').date()
            month_year = expense_date.strftime('%Y-%m')
            
            expense_data = {
                'merchant': extracted_data['merchant_name'],
                'amount_tl': conversion['tl_amount'],
                'amount_mwk': conversion['mwk_amount'],
                'rate_type': conversion['rate_type'],
                'rate_used': conversion['rate_used'],
                'expense_date': expense_date,
                'month_year': month_year,
                'items': extracted_data.get('items', []),
                'confidence': 'manual' if is_manual_entry else extracted_data.get('confidence', 'medium')
            }
            
            # Save to database
            expense = DatabaseService.save_expense(user.id, expense_data)
            
            # Get monthly total
            monthly_total = DatabaseService.get_monthly_total(user.id, month_year)
            
            # Enhanced success message with items
            entry_type = "Manual Entry" if is_manual_entry else "Receipt"
            
            # Build items summary
            items_summary = ""
            items = extracted_data.get('items', [])
            if items and len(items) > 0:
                items_summary = f"\n\n🛍️ *Items Purchased ({len(items)}):*"
                for item in items[:5]:  # Show max 5 items
                    name = item.get('name', 'Unknown')
                    price = item.get('price', 0)
                    qty = item.get('quantity', 1)
                    if qty > 1:
                        items_summary += f"\n   • {name} x{qty} - ₺{price:.2f}"
                    else:
                        items_summary += f"\n   • {name} - ₺{price:.2f}"
                
                if len(items) > 5:
                    items_summary += f"\n   • ... and {len(items) - 5} more items"
            
            # CHANGED: Format date as DD/MM/YYYY
            formatted_date = expense_data['expense_date'].strftime('%d/%m/%Y')
            
            success_message = f"""✅ {entry_type} Saved Successfully!

*This Purchase:*
🏪 {expense_data['merchant']}
💰 ₺{expense_data['amount_tl']:.2f} → {expense_data['amount_mwk']:.2f} MWK
📊 Rate: {expense_data['rate_type']} ({expense_data['rate_used']:.2f})
📅 Date: {formatted_date}{items_summary}

*Monthly Summary ({expense_data['month_year']}):*
💵 {monthly_total['mwk_total']:.2f} MWK total
₺ {monthly_total['tl_total']:.2f} TL total
🧾 {monthly_total['transaction_count']} transactions

Use "total" command to see current month anytime."""

            self.whatsapp.send_message(from_number, success_message)
            
            # Clear pending data
            if from_number in self.pending_receipts:
                del self.pending_receipts[from_number]
            if from_number in self.pending_manual_entries:
                del self.pending_manual_entries[from_number]
            if from_number in self.manual_entry_states:
                del self.manual_entry_states[from_number]
            
            logger.info(f"{'Manual entry' if is_manual_entry else 'Receipt'} saved successfully for {from_number}")
            
        except Exception as e:
            logger.error(f"Error handling rate selection: {e}")
            self.whatsapp.send_message(
                from_number,
                f"❌ Error saving transaction: {str(e)}"
            )
    
    def send_welcome_message(self, to_number):
        """Send welcome message"""
        message = """🤖 *Welcome to Dr Budget!*

This bot processes your Turkish receipts and tracks your monthly expenses in MWK.

*How to use:*
📸 Send a photo of your receipt
✅ Confirm the extracted information  
💱 Choose rate type (POS/ATM)
📊 View your monthly total

*Commands:*
- "total" - Choose month or view all-time
- "details" - View recent purchase items
- "manual" - Add expense without receipt
- "help" - Show help

Let's get started! 🚀"""

        self.whatsapp.send_message(to_number, message)
    
    def send_help_message(self, to_number):
        """Send help message"""
        message = """📋 *Help*

*Sending Receipts:*
1. Take a clear photo of your receipt
2. Send it to this bot via WhatsApp
3. Review the extracted information
4. Choose rate type (POS/ATM)

*Manual Entry (No Receipt):*
1. Send "manual" command
2. Enter amount in Turkish Lira (e.g., "45.50")
3. Enter merchant name (e.g., "Migros")
4. Choose rate type (POS/ATM)

*View Expenses:*
- "total" - Choose month or view all-time
- "details" - See recent items breakdown

*Commands:*
- "manual" - Add expense without receipt
- "details" - View recent purchase items
- "hello" or "hi" - Welcome message

*Having issues?* Make sure your receipt photo is clear and straight.

💡 *Pro tip:* Itemized receipts (like grocery stores) will show individual items in your purchase history!"""

        self.whatsapp.send_message(to_number, message)
        
    def start_manual_entry(self, from_number):
        """Start manual entry process"""
        message = """📝 *Manual Entry Mode*

I'll help you add an expense without a receipt.

*Step 1:* Please send the total amount you spent in Turkish Lira.

*Examples:*
- 45.50
- 120
- 33.75

Send just the number (with or without decimals)."""

        # Initialize manual entry state
        self.manual_entry_states[from_number] = {
            'step': 'amount',
            'awaiting_amount': True,
            'awaiting_merchant': False,
            'amount': None,
            'merchant': None
        }

        self.whatsapp.send_message(from_number, message)
        logger.info(f"Started manual entry for {from_number}")
    
    def is_amount_entry(self, text):
        """Check if text is a valid amount entry"""
        try:
            # Remove common currency symbols and whitespace
            cleaned_text = text.replace('₺', '').replace('tl', '').replace('lira', '').strip()
            
            # Try to parse as float
            amount = float(cleaned_text)
            
            # Validate amount (between 0.01 and 10000 TL)
            return 0.01 <= amount <= 10000.00
            
        except (ValueError, TypeError):
            return False
    
    def handle_manual_amount(self, from_number, user, text):
        """Handle manual amount entry"""
        try:
            # Check if user is in manual entry mode
            if from_number not in self.manual_entry_states:
                # Not in manual entry mode, send help
                self.whatsapp.send_message(
                    from_number,
                    "To add a manual entry, please send 'manual' command first."
                )
                return
            
            # Extract amount
            cleaned_text = text.replace('₺', '').replace('tl', '').replace('lira', '').strip()
            amount = float(cleaned_text)
            
            # Update state
            self.manual_entry_states[from_number].update({
                'step': 'merchant',
                'awaiting_amount': False,
                'awaiting_merchant': True,
                'amount': amount
            })
            
            # Ask for merchant
            merchant_message = f"""✅ *Amount Received: ₺{amount:.2f}*

*Step 2:* Now please tell me where you spent this money.

*Examples:*
- Migros
- Starbucks
- Taxi
- Restaurant
- Pharmacy
- Gas Station

Just type the merchant/store name:"""

            self.whatsapp.send_message(from_number, merchant_message)
            logger.info(f"Amount processed for {from_number}: ₺{amount}, awaiting merchant")
            
        except Exception as e:
            logger.error(f"Error handling manual amount: {e}")
            self.whatsapp.send_message(
                from_number,
                "❌ Invalid amount format. Please send a valid number (e.g., 45.50)"
            )
    
    def handle_manual_merchant(self, from_number, user, merchant_text):
        """Handle manual merchant entry"""
        try:
            if from_number not in self.manual_entry_states:
                return
            
            state = self.manual_entry_states[from_number]
            amount = state['amount']
            
            # Clean merchant name
            merchant_name = merchant_text.strip().title()
            
            # Validate merchant name (basic validation)
            if len(merchant_name) < 2 or len(merchant_name) > 50:
                self.whatsapp.send_message(
                    from_number,
                    "❌ Please enter a valid merchant name (2-50 characters)"
                )
                return
            
            # Create manual entry data (no items for manual entries)
            manual_data = {
                'merchant_name': merchant_name,
                'total_amount': amount,
                'date': datetime.now().strftime('%Y-%m-%d'),  # Store as YYYY-MM-DD
                'items': [],  # No items for manual entries
                'confidence': 'manual',
                'receipt_number': None,
                'tax_amount': 0
            }
            
            # Store pending manual entry
            self.pending_manual_entries[from_number] = manual_data
            
            # Create rate selection message
            pos_amount = amount * self.exchange_rate_service.pos_rate if self.exchange_rate_service else 0
            atm_amount = amount * self.exchange_rate_service.atm_rate if self.exchange_rate_service else 0
            
            # CHANGED: Display date in DD/MM/YYYY format
            display_date = datetime.now().strftime('%d/%m/%Y')
            
            confirmation_message = f"""✅ *Manual Entry Complete*

🏪 *Merchant:* {merchant_name}
💰 *Amount:* ₺{amount:.2f}
📅 *Date:* {display_date}

*Step 3:* Choose your payment method:

🏪 *POS Rate:* ₺{amount:.2f} → {pos_amount:.2f} MWK
🏧 *ATM Rate:* ₺{amount:.2f} → {atm_amount:.2f} MWK"""

            self.whatsapp.send_message(from_number, confirmation_message)
            
            # Send rate selection buttons
            self.whatsapp.send_interactive_message(
                from_number,
                "Choose your payment method:",
                [
                    {"id": "pos_rate", "title": "🏪 POS Rate"},
                    {"id": "atm_rate", "title": "🏧 ATM Rate"}
                ]
            )
            
            # Clear manual entry state (keep only pending_manual_entries for rate selection)
            del self.manual_entry_states[from_number]
            
            logger.info(f"Manual entry ready for rate selection: {merchant_name} - ₺{amount}")
            
        except Exception as e:
            logger.error(f"Error handling manual merchant: {e}")
            self.whatsapp.send_message(
                from_number,
                "❌ Error processing merchant name. Please try again."
            )