from app import create_app, mail
from flask_mail import Message
from dotenv import load_dotenv
import os

# .env ফাইল লোড
load_dotenv()  # ডিফল্ট পাথ থেকে লোড করবে, যদি .env C:\All_data\xforum-এ থাকে
app = create_app()
with app.app_context():
    # কনফিগারেশন চেক
    print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"MAIL_PASSWORD: {app.config.get('MAIL_PASSWORD')}")  # পাসওয়ার্ড দেখাতে সতর্ক থাকো
    try:
        msg = Message('Test Email', sender=app.config['MAIL_USERNAME'], recipients=['islamhriday625@gmail.com'])
        msg.body = 'This is a test email from your Flask app.'
        mail.send(msg)
        print("Test email sent successfully!")
    except Exception as e:
        print(f"Failed to send test email: {str(e)}")