from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@egov.gov.au').first():
        admin = User(
            username='admin',
            email='admin@egov.gov.au',
            password=generate_password_hash('admin123', method='pbkdf2:sha256', salt_length=8),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin created!")
    print("Database ready!")
