from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

# Flask-Mail configuration (same as in app.py)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sales.innoelectronics@gmail.com'
app.config['MAIL_PASSWORD'] = 'oghn uehu vnpl grfe'
app.config['MAIL_DEFAULT_SENDER'] = 'sales.innoelectronics@gmail.com'

mail = Mail(app)

with app.app_context():
    try:
        msg = Message('Test Email from Checkout Module', recipients=['sales.innoelectronics@gmail.com'])
        msg.body = 'This is a test email to verify the email module in checkout is working.'
        mail.send(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
