from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    whatsapp_id = db.Column(db.String(50), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to expenses
    expenses = db.relationship('Expense', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.whatsapp_id}>'

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Basic expense info
    merchant = db.Column(db.String(200))
    amount_tl = db.Column(db.Float, nullable=False)
    amount_mwk = db.Column(db.Float, nullable=False)
    
    # Exchange rate info
    rate_type = db.Column(db.String(10))  # 'POS' or 'ATM'
    rate_used = db.Column(db.Float, nullable=False)
    
    # Date tracking
    expense_date = db.Column(db.Date, nullable=False)
    month_year = db.Column(db.String(7))  # Format: '2025-06'
    
    # Additional data
    items_json = db.Column(db.Text)  # Store items as JSON string
    receipt_image_url = db.Column(db.String(500))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confidence_level = db.Column(db.String(10))  # 'high', 'medium', 'low'
    
    def set_items(self, items_list):
        """Store items as JSON"""
        self.items_json = json.dumps(items_list, ensure_ascii=False)
    
    def get_items(self):
        """Retrieve items from JSON"""
        if self.items_json:
            return json.loads(self.items_json)
        return []
    
    def __repr__(self):
        return f'<Expense {self.merchant}: ${self.amount_mwk}>'