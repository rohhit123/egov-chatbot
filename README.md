# AI-Powered E-Government Chatbot Portal
**ITS320 Capstone Project — Group B**

## Overview
A Flask-based AI chatbot portal for Australian e-government services. Citizens can get instant answers about tax, passports, Medicare, Centrelink, licences, and more — 24/7.

## Team Members
- Rohit Dahal
- Niranjan Thapa
- Jeevan Ghimire
- Yuvraj Sharma
- Rishab Sapkota

## Features
- 🤖 AI Chatbot with NLP intent matching
- 👤 Citizen registration & login
- 📋 Service request submission & tracking
- ⭐ Feedback system
- 🔧 Admin dashboard for managing requests
- 🔒 Secure password hashing

## Setup & Run

### Requirements
- Python 3.9+

### Installation
```bash
pip install -r requirements.txt
python app.py
```

### Access
- App runs at: http://localhost:5000
- Admin login: admin@egov.gov.au / admin123

## Project Structure
```
egov_chatbot/
├── app.py              # Main Flask application + chatbot logic
├── requirements.txt    # Python dependencies
├── start.sh            # Quick start script
├── templates/          # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── chatbot.html
│   ├── services.html
│   ├── feedback.html
│   └── admin.html
├── static/
│   ├── css/style.css   # Stylesheet
│   └── js/main.js      # JavaScript
└── instance/           # SQLite database (auto-created)
```

## Technologies Used
- **Backend**: Python, Flask, Flask-Login, Flask-SQLAlchemy
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **NLP**: Keyword-based intent classification
- **Security**: Werkzeug PBKDF2 password hashing
