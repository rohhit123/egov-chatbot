from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from openai import OpenAI
import os
import json
import random
import requests as http_requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "egov_secret_key_2024")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///egov_chatbot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------ Models ------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), default='citizen')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    started_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    messages = db.Column(db.Text, default='[]')

class ServiceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    reference_number = db.Column(db.String(20), unique=True)
    submitted_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    submitted_at = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

# ------------------ Login Manager ------------------

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ------------------ Knowledge Base (fallback) ------------------

KNOWLEDGE_BASE = {
    "tax": {
        "keywords": ["tax", "taxes", "filing", "return", "ato", "income tax", "gst", "refund",
                     "tax return", "lodge", "lodging", "lodgement", "taxable", "deduction",
                     "deductions", "financial year", "fy", "tfn", "tax file number",
                     "withholding", "payg", "pay as you go", "tax offset", "medicare levy",
                     "capital gains", "cgt", "tax agent", "bas", "business activity",
                     "tax debt", "owe tax", "tax bill", "tax help", "tax office"],
        "response": "For <b>Tax & ATO</b> queries:<br><br>"
                    "• Lodge your tax return at <a href='https://www.ato.gov.au' target='_blank'>ato.gov.au</a> or via myGov<br>"
                    "• Tax filing deadline: <b>31 October</b> each year<br>"
                    "• Track your refund via myGov → ATO → Tax → Lodgments<br>"
                    "• GST registration required if annual turnover exceeds <b>$75,000</b><br>"
                    "• TFN applications: visit ato.gov.au/tfn<br>"
                    "• Tax debts: payment plans available — call ATO on <b>13 28 61</b><br><br>"
                    "Would you like to submit a service request for tax assistance?"
    },
    "birth_certificate": {
        "keywords": ["birth", "certificate", "birth certificate", "register birth", "newborn",
                     "born", "baby", "births deaths marriages", "bdm", "vital record",
                     "birth registration", "copy", "certified copy", "duplicate certificate",
                     "replace certificate", "get a copy", "make a copy"],
        "response": "For <b>Birth Certificates</b>:<br><br>"
                    "• Register at your State's Births, Deaths & Marriages (BDM) registry<br>"
                    "• <b>NSW:</b> bdm.nsw.gov.au | <b>VIC:</b> births.vic.gov.au | <b>QLD:</b> qld.gov.au/bdm<br>"
                    "• Processing time: <b>5–10 business days</b> (standard), <b>3 days</b> (priority)<br>"
                    "• Fee: approx. <b>$50–$65 AUD</b> depending on state<br>"
                    "• Certified copies available — apply through your state BDM registry<br>"
                    "• Newborns must be registered within <b>60 days</b> of birth<br><br>"
                    "Would you like to submit a service request for a birth certificate?"
    },
    "passport": {
        "keywords": ["passport", "travel document", "overseas travel", "renew passport",
                     "passport renewal", "passport application", "apply passport", "new passport",
                     "lost passport", "stolen passport", "passport photo", "passport fee",
                     "international travel", "emergency passport", "urgent passport",
                     "passport expire", "expired passport"],
        "response": "For <b>Passport Services</b>:<br><br>"
                    "• Apply or renew at <a href='https://www.passports.gov.au' target='_blank'>passports.gov.au</a><br>"
                    "• <b>Standard processing:</b> 6 weeks | <b>Priority:</b> 2 weeks (extra fee)<br>"
                    "• <b>Adult fee:</b> $308 AUD | <b>Child (under 16):</b> $156 AUD<br>"
                    "• Lost/stolen passport: report to police first, then apply for replacement<br>"
                    "• Emergency passports available — call <b>131 232</b><br><br>"
                    "Would you like to submit a passport service request?"
    },
    "license": {
        "keywords": ["license", "licence", "driver", "driving", "vehicle registration", "car rego",
                     "rego", "registration", "renew licence", "learner", "l plate", "p plate",
                     "provisional", "full licence", "lost licence", "suspended", "demerit",
                     "demerit points", "speeding", "fine", "roadworthy", "pink slip",
                     "driving test", "knowledge test", "my car", "car expired", "car registration"],
        "response": "For <b>Driver's Licence & Vehicle Registration</b>:<br><br>"
                    "• Renew licence online via your state transport website:<br>"
                    "&nbsp;&nbsp;– <b>NSW:</b> service.nsw.gov.au | <b>VIC:</b> vicroads.vic.gov.au | <b>QLD:</b> qld.gov.au/transport<br>"
                    "• P1 → P2: Must hold P1 for <b>12 months</b> | P2 → Full: <b>24 months</b><br>"
                    "• Lost licence replacement: approx. <b>$25 AUD</b><br>"
                    "• Vehicle rego renewal notices sent <b>4–6 weeks</b> before expiry<br><br>"
                    "Would you like to submit a licensing service request?"
    },
    "healthcare": {
        "keywords": ["medicare", "healthcare", "health card", "medical", "bulk billing", "hospital",
                     "doctor", "gp", "general practitioner", "specialist", "referral", "health",
                     "medicare card", "enrol medicare", "health insurance", "ambulance",
                     "pharmacy", "prescription", "pbs", "pharmaceutical benefits",
                     "mental health", "psychologist", "mental health plan", "better access"],
        "response": "For <b>Medicare & Healthcare</b>:<br><br>"
                    "• Enrol or update Medicare at <a href='https://my.gov.au' target='_blank'>my.gov.au</a><br>"
                    "• Replace Medicare card: Free via myGov app → Medicare<br>"
                    "• <b>Bulk billing</b> = GP charges Medicare directly, no out-of-pocket cost<br>"
                    "• <b>Mental Health Care Plan:</b> ask your GP — up to 10 subsidised psychology sessions/year<br>"
                    "• Emergency: Call <b>000</b> | Health advice: <b>1800 022 222</b><br><br>"
                    "Would you like to submit a healthcare service request?"
    },
    "centrelink": {
        "keywords": ["centrelink", "welfare", "payment", "jobseeker", "newstart", "benefit",
                     "allowance", "youth allowance", "austudy", "family payment",
                     "family tax benefit", "ftb", "parenting payment", "disability support",
                     "dsp", "aged pension", "pension", "carer payment", "services australia",
                     "income support", "mutual obligation", "reporting income", "lost my job",
                     "lost job", "unemployed", "no income", "financial help", "financial support",
                     "need money", "government payment", "apply centrelink"],
        "response": "For <b>Centrelink / Services Australia</b>:<br><br>"
                    "• Apply for payments at <a href='https://my.gov.au' target='_blank'>my.gov.au</a> → Centrelink<br>"
                    "• <b>JobSeeker Payment:</b> For people aged 22–67 looking for work<br>"
                    "• <b>Youth Allowance:</b> For students and job seekers aged 16–24<br>"
                    "• <b>Disability Support Pension (DSP):</b> For permanent physical/mental conditions<br>"
                    "• <b>Age Pension:</b> Available from age 67<br>"
                    "• <b>Family Tax Benefit:</b> For families with children under 18<br>"
                    "• Call Centrelink: <b>136 240</b> (Families) | <b>132 850</b> (Job seekers)<br><br>"
                    "Would you like to submit a Centrelink service request?"
    },
    "council": {
        "keywords": ["council", "rates", "rubbish", "bin", "local government", "parking",
                     "noise complaint", "council rates", "garbage", "recycling", "green waste",
                     "hard rubbish", "development application", "da", "building permit",
                     "planning permit", "local council", "parking fine", "parking ticket"],
        "response": "For <b>Local Council Services</b>:<br><br>"
                    "• Pay council rates online via your local council website<br>"
                    "• Find your council: <a href='https://www.lga.asn.au' target='_blank'>lga.asn.au</a><br>"
                    "• <b>Noise complaints:</b> lodge with your local council<br>"
                    "• <b>Development applications (DAs):</b> submit through your council's planning portal<br>"
                    "• <b>Parking fines:</b> dispute through your local council or state revenue office<br><br>"
                    "Would you like to submit a council-related service request?"
    },
    "complaint": {
        "keywords": ["complaint", "complain", "issue", "problem", "unhappy", "dissatisfied",
                     "escalate", "not happy", "poor service", "bad service",
                     "ombudsman", "appeal", "dispute", "grievance", "wrong information",
                     "mistake", "error", "incorrect"],
        "response": "For <b>Complaints & Escalations</b>:<br><br>"
                    "• Submit a formal complaint via the <a href='/services'>Services page</a><br>"
                    "• Most complaints acknowledged within <b>2 business days</b><br>"
                    "• <b>Commonwealth Ombudsman:</b> ombudsman.gov.au | 1300 362 072<br>"
                    "• <b>ATO complaints:</b> ato.gov.au/complaints<br>"
                    "• <b>Centrelink complaints:</b> servicesaustralia.gov.au/complaints<br><br>"
                    "Would you like to submit a formal complaint now?"
    },
    "housing": {
        "keywords": ["housing", "rent", "rental", "house", "home", "accommodation", "public housing",
                     "social housing", "homeless", "homelessness", "shelter", "bond", "rental bond",
                     "tenancy", "tenant", "landlord", "lease", "eviction", "notice to vacate",
                     "first home buyer", "first home", "stamp duty", "home loan", "mortgage"],
        "response": "For <b>Housing & Tenancy</b>:<br><br>"
                    "• <b>Public/social housing:</b> apply through your state housing authority<br>"
                    "&nbsp;&nbsp;– NSW: facs.nsw.gov.au | VIC: housing.vic.gov.au | QLD: housing.qld.gov.au<br>"
                    "• <b>Tenant rights:</b> contact your state's tenancy authority<br>"
                    "• <b>First Home Buyer Grant:</b> available in most states<br>"
                    "• <b>Homelessness support:</b> call <b>1800 HOUSING</b> (1800 468 746) — 24/7<br><br>"
                    "Would you like to submit a housing-related service request?"
    },
    "education": {
        "keywords": ["education", "school", "university", "tafe", "study", "student", "enrol",
                     "scholarship", "austudy", "hecs", "help debt", "student loan",
                     "childcare", "child care", "kindergarten", "preschool", "ccs",
                     "childcare subsidy", "myskills", "training"],
        "response": "For <b>Education & Training</b>:<br><br>"
                    "• <b>HECS-HELP:</b> Government loan for eligible university students<br>"
                    "• <b>HELP debt repayment</b> starts when income exceeds ~$51,550/year<br>"
                    "• <b>Childcare Subsidy (CCS):</b> Apply via myGov → Centrelink — up to 90% subsidy<br>"
                    "• <b>MySkills:</b> myskills.gov.au — find TAFE and training courses near you<br>"
                    "• <b>Austudy/Youth Allowance:</b> financial support for eligible full-time students<br><br>"
                    "Would you like to submit an education-related service request?"
    },
    "immigration": {
        "keywords": ["immigration", "visa", "migrate", "migration", "citizenship", "permanent residency",
                     "pr", "skilled visa", "partner visa", "student visa", "work visa",
                     "tourist visa", "visitor visa", "bridging visa", "asylum", "refugee",
                     "home affairs", "naturalisation", "become australian", "australian citizen",
                     "citizenship test", "sponsorship"],
        "response": "For <b>Visas, Immigration & Citizenship</b>:<br><br>"
                    "• All visa applications: <a href='https://immi.homeaffairs.gov.au' target='_blank'>immi.homeaffairs.gov.au</a><br>"
                    "• <b>Skilled visas:</b> subclass 189, 190, 491 — based on points test<br>"
                    "• <b>Student visa (subclass 500):</b> apply after receiving university/TAFE offer<br>"
                    "• <b>Australian Citizenship:</b> must hold PR for 4 years and pass citizenship test<br>"
                    "• Department of Home Affairs: <b>131 881</b><br><br>"
                    "Would you like to submit an immigration-related service request?"
    },
    "business": {
        "keywords": ["business", "abn", "acn", "register business", "business registration",
                     "company", "sole trader", "partnership", "business name", "asic",
                     "fair work", "workplace", "employee", "employer", "payroll",
                     "superannuation", "super", "superannuation guarantee", "workers comp",
                     "small business", "run business", "start business", "open business",
                     "own business", "need abn", "freelance", "self employed", "contractor"],
        "response": "For <b>Business & Employer Services</b>:<br><br>"
                    "• <b>ABN registration:</b> Free at abr.gov.au — takes about 15 minutes<br>"
                    "• <b>Yes, you need an ABN</b> to run a business legally in Australia<br>"
                    "• <b>Business name registration:</b> asic.gov.au — $42 (1 year) or $98 (3 years)<br>"
                    "• <b>Superannuation Guarantee:</b> Employers must pay 11.5% super on wages<br>"
                    "• <b>Fair Work:</b> fairwork.gov.au — minimum wages, entitlements, disputes<br>"
                    "• <b>GST registration</b> required if turnover exceeds $75,000/year<br><br>"
                    "Would you like to submit a business-related service request?"
    },
    "status": {
        "keywords": ["status", "track", "application", "reference", "check", "progress",
                     "how long", "waiting", "wait time", "processing time", "update",
                     "follow up", "check my", "my application", "my request", "sr-",
                     "reference number", "tracking", "when will"],
        "response": "For <b>Application Status Tracking</b>:<br><br>"
                    "• Visit your <a href='/dashboard'>dashboard</a> to see all your service requests<br>"
                    "• Typical processing times:<br>"
                    "&nbsp;&nbsp;– Tax return: <b>2 weeks</b> (e-lodgement)<br>"
                    "&nbsp;&nbsp;– Passport (standard): <b>6 weeks</b><br>"
                    "&nbsp;&nbsp;– Birth certificate: <b>5–10 business days</b><br>"
                    "&nbsp;&nbsp;– Medicare enrolment: <b>3–4 weeks</b><br>"
                    "• Go to your <a href='/services'>services page</a> to view all requests."
    },
    "hours": {
        "keywords": ["hours", "open", "operating", "when", "time", "available", "office",
                     "business hours", "after hours", "weekend", "saturday", "sunday",
                     "public holiday", "close", "closed", "opening time"],
        "response": "For <b>Service Hours & Availability</b>:<br><br>"
                    "• 🤖 This AI chatbot: <b>Available 24/7</b><br>"
                    "• 📞 Phone support: <b>Monday–Friday, 8:00 AM – 5:00 PM AEST</b><br>"
                    "• 🏢 Walk-in service centres: <b>Monday–Friday, 9:00 AM – 4:30 PM</b><br>"
                    "• 🎉 Public holidays: limited phone support only<br><br>"
                    "Is there a specific service I can help you with today?"
    },
    "mygov": {
        "keywords": ["mygov", "my gov", "mygov account", "mygov login", "link", "link account",
                     "mygov help", "cant login", "can't login", "forgot password", "reset password",
                     "mygov app", "myid", "mygovid", "new password", "password help"],
        "response": "For <b>myGov Account Help</b>:<br><br>"
                    "• Access myGov at <a href='https://my.gov.au' target='_blank'>my.gov.au</a> or via the myGov app<br>"
                    "• <b>Forgot password:</b> my.gov.au → 'Forgot password' → enter your email<br>"
                    "• <b>Reset password:</b> check your email for a reset link from myGov<br>"
                    "• <b>Link services:</b> After login → Services → Add (ATO, Medicare, Centrelink)<br>"
                    "• <b>myGovID:</b> Digital identity app — download from App Store/Google Play<br>"
                    "• <b>myGov support:</b> 132 307 (Mon–Fri 7am–10pm, Sat–Sun 10am–5pm AEST)<br><br>"
                    "Would you like to submit a myGov-related service request?"
    },
    "car_insurance": {
        "keywords": ["car insurance", "vehicle insurance", "insurance", "insure", "ctp",
                     "compulsory third party", "third party", "comprehensive",
                     "car accident", "accident", "crash", "collision", "smash repair",
                     "write off", "written off", "claim insurance"],
        "response": "For <b>Car Insurance & CTP</b>:<br><br>"
                    "• <b>CTP (Compulsory Third Party)</b> is required by law — included with your rego<br>"
                    "• CTP covers personal injury to others only — not vehicle damage<br>"
                    "• <b>Comprehensive insurance</b> covers vehicle damage — through private insurers<br>"
                    "• After an accident: exchange details, take photos, report to police if needed<br>"
                    "• <b>CTP claims:</b> NSW: sira.nsw.gov.au | VIC: tac.vic.gov.au | QLD: ctp.qld.gov.au<br>"
                    "• Insurance disputes: <b>AFCA</b> at afca.org.au<br><br>"
                    "Would you like help with your vehicle registration instead?"
    },
    "yes_no": {
        "keywords": ["yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright", "please",
                     "no", "nope", "nah", "not now", "i do", "i would", "go ahead",
                     "should i", "do i need", "do i have to", "is it required",
                     "how do i start", "where do i start", "what do i do"],
        "response": "Sure! You can submit a service request on the "
                    "<a href='/services'>Services page</a> — select your service type, "
                    "describe your situation, and you'll receive a reference number instantly.<br><br>"
                    "Is there anything else I can help clarify?"
    },
    "hello": {
        "keywords": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening",
                     "g'day", "howdy", "greetings", "sup", "what's up", "whats up", "yo"],
        "response": "G'day! Welcome to the <b>Australian E-Government Service Portal</b>! 🇦🇺<br><br>"
                    "I'm <b>GovAssist AI</b>, your 24/7 government services assistant. I can help you with:<br><br>"
                    "🏛️ <b>Identity & Documents</b> — Birth certificates, Passports, Driver's licence<br>"
                    "💰 <b>Tax & Financial</b> — ATO, Tax returns, GST, Business registration<br>"
                    "🏥 <b>Health</b> — Medicare, PBS, Mental health plans<br>"
                    "🤝 <b>Centrelink</b> — JobSeeker, Aged Pension, Family payments<br>"
                    "🎓 <b>Education</b> — HECS-HELP, Childcare subsidy, TAFE<br>"
                    "✈️ <b>Immigration</b> — Visas, Citizenship, Permanent residency<br>"
                    "🏘️ <b>Council & Housing</b> — Rates, Tenancy, Public housing<br>"
                    "💼 <b>Business</b> — ABN, Super, Fair Work<br><br>"
                    "Just type your question or click a topic on the left!"
    },
    "help": {
        "keywords": ["help", "assist", "support", "what can you do", "services", "options",
                     "menu", "topics", "what do you know", "capabilities", "features"],
        "response": "Here's everything I can help you with:<br><br>"
                    "🏛️ <b>Identity & Documents</b> — Birth/Death/Marriage certificates, Passport, Driver's licence<br>"
                    "💰 <b>Tax & Finance</b> — Income tax, GST, PAYG, BAS, ABN<br>"
                    "🏥 <b>Health & Medicare</b> — Medicare card, Bulk billing, PBS, Mental health plans<br>"
                    "🤝 <b>Centrelink</b> — JobSeeker, Youth Allowance, DSP, Age Pension, Family payments<br>"
                    "✈️ <b>Visas & Immigration</b> — Visa applications, Citizenship<br>"
                    "🎓 <b>Education</b> — HECS-HELP, Childcare Subsidy, Austudy<br>"
                    "🏘️ <b>Housing & Council</b> — Public housing, Tenancy, Council rates<br>"
                    "💼 <b>Business</b> — ABN, Super, Fair Work, Workers comp<br>"
                    "💻 <b>myGov Account</b> — Login help, password reset, linking services<br><br>"
                    "Just type your question naturally!"
    },
    "thanks": {
        "keywords": ["thank", "thanks", "thank you", "cheers", "appreciate", "great", "awesome",
                     "helpful", "perfect", "excellent", "good job", "well done", "brilliant"],
        "response": "You're welcome! 😊 Happy to help!<br><br>"
                    "I'm here <b>24/7</b> — come back any time you need help with government services.<br><br>"
                    "Is there anything else I can assist you with today?"
    },
    "goodbye": {
        "keywords": ["bye", "goodbye", "see you", "later", "farewell", "that's all", "thats all",
                     "done", "finished", "no thanks", "nothing else"],
        "response": "Thanks for using the E-Government Portal! 👋<br><br>"
                    "Have a great day — I'm available <b>24/7</b> whenever you need help. Take care! 🇦🇺"
    },
}

# ------------------ Chatbot System Prompt ------------------

SYSTEM_PROMPT = """You are GovAssist AI, a friendly and professional Australian e-government assistant helping citizens 24/7.

You help Australian citizens with:
- Tax and ATO: tax returns, TFN, GST, PAYG, BAS, refunds, tax debts
- Passports: apply, renew, lost, emergency, fees, processing times
- Driver licence and vehicle registration: renew, lost, demerit points, rego
- Medicare: enrol, replace card, bulk billing, PBS, mental health plan
- Centrelink: JobSeeker, Age Pension, Youth Allowance, DSP, Family Tax Benefit
- Birth death marriage certificates: apply, fees, BDM registry, certified copies
- Visas and immigration: skilled visa, student visa, partner visa, citizenship
- myGov account: login help, linking services, password reset, myGovID
- Business: ABN, ACN, superannuation, Fair Work, GST registration
- Council services: rates, bins, parking fines, development applications
- Housing: public housing, rental bonds, tenant rights, first home buyer
- Education: HECS-HELP, childcare subsidy, Austudy, Youth Allowance
- Car insurance: CTP, comprehensive, accident claims

Rules:
- Be friendly, warm and conversational
- Understand natural language — short phrases like 'yes', 'my car', 'lost my job' etc
- Use Australian English: licence, centre, organisation
- Give specific accurate info with phone numbers and websites where helpful
- Keep responses under 150 words
- Use bullet points for clarity
- If not government related, politely say you specialise in Australian government services
- Always offer to help submit a service request when relevant
- Never give specific legal or financial advice"""

# ------------------ Chatbot Logic ------------------

def get_bot_response(user_message):
    """Try Ollama first (local Mac), then OpenRouter (Render), then keywords (always works)."""

    # Try Ollama first — works on local Mac with Ollama running
    try:
        response = http_requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2",
                "stream": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ]
            },
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Ollama responded")
            return response.json()["message"]["content"]
    except Exception as e:
        print(f"Ollama not available: {e}")

    # Try OpenRouter with correct model
    try:
        if OPENROUTER_API_KEY:
            print(f"Attempting OpenRouter with API key: {OPENROUTER_API_KEY[:10]}...")
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY
            )
            
            # Try multiple models if first fails
            models_to_try = [
                "mistralai/mistral-7b-instruct",  # No :free suffix
                "google/gemma-2-2b-it:free",      # Free tier model
                "microsoft/phi-2:free",            # Another free model
                "nousresearch/hermes-3-llama-3.1-8b:free"
            ]
            
            for model in models_to_try:
                try:
                    print(f"Trying model: {model}")
                    completion = client.chat.completions.create(
                        model=model,
                        max_tokens=400,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message}
                        ],
                        timeout=15
                    )
                    print(f"✅ OpenRouter responded with {model}")
                    return completion.choices[0].message.content
                except Exception as model_error:
                    print(f"Model {model} failed: {model_error}")
                    continue
        else:
            print("No OpenRouter API key found")
    except Exception as e:
        print(f"OpenRouter not available: {e}")

    # Final fallback — keywords always work
    print("Using keyword fallback")
    return keyword_fallback(user_message)

def keyword_fallback(user_message):
    """Keyword matcher when AI is unavailable."""
    msg = user_message.lower().strip()
    best_match = None
    best_score = 0
    for intent, data in KNOWLEDGE_BASE.items():
        score = sum(1 for kw in data["keywords"] if kw in msg)
        if score > best_score:
            best_score = score
            best_match = intent
    if best_match and best_score > 0:
        return KNOWLEDGE_BASE[best_match]["response"]
    return ("I'm not quite sure about that. Here are some things I can help with:<br><br>"
            "💬 Try asking me something like:<br>"
            "&nbsp;&nbsp;• <b>'I need to renew my passport'</b><br>"
            "&nbsp;&nbsp;• <b>'Help with my tax return'</b><br>"
            "&nbsp;&nbsp;• <b>'How do I get a Medicare card?'</b><br>"
            "&nbsp;&nbsp;• <b>'I need Centrelink payment help'</b><br>"
            "&nbsp;&nbsp;• <b>'Register a business ABN'</b><br>"
            "&nbsp;&nbsp;• <b>'My car registration renewal'</b><br><br>"
            "Or type <b>'help'</b> to see all topics.")

# ------------------ Routes ------------------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful! Welcome back.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "error")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return redirect(url_for('register'))
        hashed = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
        new_user = User(username=username, email=email, password=hashed)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    requests_count = ServiceRequest.query.filter_by(user_id=current_user.id).count()
    pending_count = ServiceRequest.query.filter_by(user_id=current_user.id, status='Pending').count()
    recent_requests = ServiceRequest.query.filter_by(user_id=current_user.id).order_by(ServiceRequest.id.desc()).limit(5).all()
    return render_template('dashboard.html',
                           requests_count=requests_count,
                           pending_count=pending_count,
                           recent_requests=recent_requests)

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    try:
        data = request.get_json(force=True, silent=True) or {}
        user_message = (data.get('message') or '').strip()
        if not user_message:
            return jsonify({'response': 'Please enter a message.'})
        bot_response = get_bot_response(user_message)
        try:
            session_record = ChatSession.query.filter_by(
                user_id=current_user.id
            ).order_by(ChatSession.id.desc()).first()
            if not session_record:
                session_record = ChatSession(user_id=current_user.id, messages='[]')
                db.session.add(session_record)
            existing = session_record.messages or '[]'
            messages = json.loads(existing)
            now = datetime.now().strftime("%H:%M")
            messages.append({'role': 'user', 'content': user_message, 'time': now})
            messages.append({'role': 'bot', 'content': bot_response, 'time': now})
            session_record.messages = json.dumps(messages)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({'response': bot_response})
    except Exception as e:
        return jsonify({'response': 'Sorry, something went wrong. Please try again.'})

@app.route('/services', methods=['GET', 'POST'])
@login_required
def services():
    if request.method == 'POST':
        service_type = request.form['service_type']
        description = request.form['description']
        ref_num = f"SR-{random.randint(100000, 999999)}"
        new_req = ServiceRequest(
            user_id=current_user.id,
            service_type=service_type,
            description=description,
            reference_number=ref_num
        )
        db.session.add(new_req)
        db.session.commit()
        flash(f"Service request submitted! Your reference number is <strong>{ref_num}</strong>.", "success")
        return redirect(url_for('services'))
    my_requests = ServiceRequest.query.filter_by(user_id=current_user.id).order_by(ServiceRequest.id.desc()).all()
    return render_template('services.html', requests=my_requests)

@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form.get('comment', '')
        fb = Feedback(user_id=current_user.id, rating=rating, comment=comment)
        db.session.add(fb)
        db.session.commit()
        flash("Thank you for your feedback!", "success")
        return redirect(url_for('dashboard'))
    return render_template('feedback.html')

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash("Access denied.", "error")
        return redirect(url_for('dashboard'))
    all_requests = ServiceRequest.query.order_by(ServiceRequest.id.desc()).all()
    all_users = User.query.all()
    avg_rating = db.session.query(db.func.avg(Feedback.rating)).scalar() or 0
    return render_template('admin.html',
                           requests=all_requests,
                           users=all_users,
                           avg_rating=round(avg_rating, 1))

@app.route('/admin/update_status/<int:req_id>', methods=['POST'])
@login_required
def update_status(req_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    req = ServiceRequest.query.get_or_404(req_id)
    req.status = request.form['status']
    req.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    db.session.commit()
    flash("Status updated.", "success")
    return redirect(url_for('admin'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

# ------------------ Run ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@egov.gov.au').first():
            admin_user = User(
                username='admin',
                email='admin@egov.gov.au',
                password=generate_password_hash('admin123', method='pbkdf2:sha256', salt_length=8),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: admin@egov.gov.au / admin123")
    app.run(debug=True, port=5000)

# ------------------ Database Init for Render (gunicorn) ------------------
# This runs when gunicorn imports the app module
with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(email='admin@egov.gov.au').first():
            admin_user = User(
                username='admin',
                email='admin@egov.gov.au',
                password=generate_password_hash('admin123', method='pbkdf2:sha256', salt_length=8),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created!")
        print("Database initialized!")
    except Exception as e:
        print(f"DB init error: {e}")