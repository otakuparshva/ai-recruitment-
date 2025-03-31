import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.utils.config import config
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        if not config.EMAIL_USER or not config.EMAIL_PASS:
            logger.warning("Email credentials not configured")
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_USER
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(config.EMAIL_HOST, config.EMAIL_PORT) as server:
                server.starttls()
                server.login(config.EMAIL_USER, config.EMAIL_PASS)
                server.send_message(msg)
                
            logger.info(f"Email sent to {recipient}: {subject}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP Authentication Error: Check your email credentials.")
            return False
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False