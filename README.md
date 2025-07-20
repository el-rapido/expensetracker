# WhatsApp Receipt Processing Agent (Dr Budget)

This is a personal WhatsApp bot that processes Turkish and English purchase receipts, extracts data using OCR, preprocesses the data using Google Gemini, converts Turkish Lira to Malawi Kwacha, and tracks monthly expenses with automated reporting through SMS.

## 🌟 Features

- **📸 Receipt Processing**: Send receipt photos via WhatsApp and get automatic data extraction through Google Cloud Vision OCR
- **🤖 AI-Powered**: Uses Google Gemini LLM for accurate Turkish receipt processing
- **💱 Currency Conversion**: Hardcoded TRY to MWK exchange rates (POS/ATM)
- **📊 Monthly Tracking**: Automatic expense tracking with monthly summaries
- **📱 Dual Delivery**: Monthly reports via both WhatsApp and SMS
- **✋ Manual Entry**: Add expenses without receipts
- **📈 Analytics**: Detailed spending insights and merchant breakdown

## 🏗️ Architecture

```
WhatsApp Bot (User Interface)
       ↓
Flask Application (app.py)
       ↓
Message Handler (processes commands/images)
       ↓
OCR Service (Google Cloud Vision) → LLM Service (Google Gemini)
       ↓
Exchange Rate Service (hardcoded rates)
       ↓
Database Service (PostgreSQL)
       ↓
Monthly Tracking + SMS/WhatsApp Delivery
```

## 🛠️ Tech Stack

- **Backend**: Flask (Python 3.11)
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **APIs**: 
  - WhatsApp Business API
  - Google Cloud Vision (OCR)
  - Google Gemini (LLM)
  - Amazon SNS (SMS)
- **Scheduling**: APScheduler
- **Hosting**: Render (free tier)

## 📋 Prerequisites

1. **WhatsApp Business API Access**
   - Facebook Developer Account
   - WhatsApp Business App
   - Verified phone number

2. **Google Cloud Services**
   - Google Cloud Vision API enabled
   - Google Gemini API access
   - Service account credentials

3. **AWS Account** (for SMS)
   - Amazon SNS service
   - AWS access keys

## 🚀 Quick Setup

### 1. Clone and Install
```bash
git clone https://github.com/el-rapido/expensetracker.git
cd expensetracker
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file:
```env
# WhatsApp Business API
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# Google APIs
GEMINI_API_KEY=your_gemini_key
GOOGLE_APPLICATION_CREDENTIALS=google-credentials.json

# AWS (SMS)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
AWS_SNS_SENDER_ID=YOURID

# Exchange Rates (MWK per 1 TL)
POS_RATE=51.00
ATM_RATE=54.00

# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Security
SECRET_KEY=your_secret_key
```

### 3. Google Credentials
Place your `google-credentials.json` file in the project root, or set `GOOGLE_CREDENTIALS_JSON` environment variable with the JSON content.

### 4. Database Setup
```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from models import db; db.create_all()"
```

### 5. Run Locally
```bash
python app.py
```

## 💬 Usage

### Basic Commands
- **"hi" / "hello"** - Welcome message
- **"help"** - Show help information
- **"total"** - View monthly/all-time expenses
- **"manual"** - Add expense without receipt

### Receipt Processing Workflow
1. 📸 Send receipt photo to WhatsApp bot
2. 🤖 Bot extracts data using OCR + AI
3. ✅ Confirm extracted information
4. 💱 Choose exchange rate (POS/ATM)
5. 💾 Expense saved to database
6. 📊 Get monthly summary update

### Manual Entry Workflow
1. 📝 Send "manual" command
2. 💰 Enter amount in Turkish Lira
3. 🏪 Enter merchant name
4. 💱 Choose exchange rate (POS/ATM)
5. ✅ Expense saved

## 📊 Monthly Automation

- **Automated Reports**: First day of each month at 9:00 AM
- **Dual Delivery**: Reports sent via both WhatsApp and SMS
- **Rich Analytics**: Top merchants, spending patterns, rate breakdown

## 🧪 Testing

### Local Testing
```bash
# Test database
curl http://localhost:5000/test-db

# Test receipt processing
curl http://localhost:5000/test-interface

# Test WhatsApp integration
curl http://localhost:5000/test-whatsapp-text/YOUR_PHONE_NUMBER
```

## 📁 Project Structure

```
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── models.py              # Database models
├── requirements.txt       # Python dependencies
├── runtime.txt            # Python version
├── render.yaml           # Render deployment config
├── google-credentials.json # Google service account (local only)
├── services/
│   ├── message_handler.py     # WhatsApp message processing
│   ├── ocr_service.py         # Google Cloud Vision integration
│   ├── llm_service.py         # Google Gemini integration
│   ├── whatsapp_service.py    # WhatsApp API wrapper
│   ├── sms_service.py         # AWS SNS integration
│   ├── exchange_rate_service.py # Currency conversion
│   ├── database_service.py    # Database operations
│   ├── monthly_tracking_service.py # Monthly reports
│   ├── scheduler_service.py   # Background jobs
│   └── receipt_workflow.py   # Complete receipt processing
└── .env                   # Environment variables (local only)
```

## 🔧 Configuration

### Exchange Rates
Update hardcoded rates in `.env`:
```env
POS_RATE=51.00  # MWK per 1 TL for POS transactions
ATM_RATE=54.00  # MWK per 1 TL for ATM withdrawals
```

### Scheduled Jobs
Monthly summaries run automatically. To modify schedule, edit `scheduler_service.py`:
```python
# Current: 1st day of month at 9:00 AM
trigger=CronTrigger(day=1, hour=9, minute=0)
```

## 🐛 Troubleshooting

### Common Issues

1. **WhatsApp webhook not receiving messages**
   - Check webhook URL in Facebook Developer Console
   - Verify `WHATSAPP_VERIFY_TOKEN` matches

2. **OCR not working**
   - Ensure Google credentials are properly set
   - Check Google Cloud Vision API is enabled

3. **SMS not sending**
   - Verify AWS credentials and SNS permissions
   - Check phone number format (+265...)

4. **Database errors**
   - Verify `DATABASE_URL` is correct
   - Check PostgreSQL connection

### Debug Endpoints
- `/health` - Service health check
- `/debug-env` - Environment variables check
- `/debug-aws` - AWS configuration check
- `/delivery-stats` - Delivery services status

## 📈 Monitoring

### Key Metrics
- Receipt processing success rate
- Monthly report delivery status
- Database connection health
- API response times

### Logs
Monitor application logs in Render dashboard for:
- Receipt processing errors
- WhatsApp API failures
- Database connection issues
- Scheduled job execution

## 🔐 Security

- Environment variables for all sensitive data
- Google service account with minimal permissions
- AWS IAM user with SNS-only access
- No hardcoded credentials in code

## 🚦 API Limits

- **WhatsApp Business API**: 1000 free messages/month
- **Google Cloud Vision**: 1000 free requests/month
- **Google Gemini**: Generous free tier
- **AWS SNS**: Pay per SMS (varies by region)



## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Google Cloud** for Vision and Gemini APIs
- **Meta** for WhatsApp Business API
- **Render** for free hosting
- **AWS** for SMS delivery via SNS

---

**Dr Budget** - Making expense tracking effortless, one receipt at a time! 🚀
