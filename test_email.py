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

# Test the async function
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email_async(msg):
    with app.app_context():
        try:
            mail.send(msg)
            logger.info("Async email sent successfully")
        except Exception as e:
            logger.error(f"Failed to send async email: {str(e)}")

# Test async email
with app.app_context():
    msg = Message('Async Test Email', recipients=['sales.innoelectronics@gmail.com'])
    msg.body = 'This is a test of async email sending.'
    thread = threading.Thread(target=send_email_async, args=(msg,))
    thread.start()
    thread.join()  # Wait for the thread to complete
    print("Async email test completed.")
