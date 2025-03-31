#!/usr/bin/env python3
import sys
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import Qt, QTranslator, QLocale
from app.ui.auth_window import AuthWindow
from app.database.session import db_session, init_db
from app.database.mongo import MongoDB
from app.utils.config import config
from app.utils.security import SecurityUtils
from app.services.email_service import EmailService

def configure_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('recruitment_system.log'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger('passlib').setLevel(logging.WARNING)

def initialize_database():
    """Initialize and verify database connections"""
    try:
        # Initialize SQL Database
        init_db()
        
        # Initialize MongoDB
        MongoDB()
        
        # Verify connections
        db_session.execute("SELECT 1")
        logging.info("Database connections established successfully")
    except Exception as e:
        logging.critical(f"Database initialization failed: {str(e)}")
        QMessageBox.critical(
            None,
            "Database Error",
            f"Failed to initialize database:\n{str(e)}"
        )
        sys.exit(1)

def configure_application(app):
    """Configure application settings and styles"""
    # Load fonts
    QFontDatabase.addApplicationFont(":/fonts/Roboto-Regular.ttf")
    QFontDatabase.addApplicationFont(":/fonts/Roboto-Medium.ttf")
    
    # Set default font
    font = QFont("Roboto", 10)
    app.setFont(font)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set application attributes
    app.setApplicationName("Recruitment System")
    app.setApplicationVersion("1.0.0")
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    
    # Load translations
    translator = QTranslator()
    if translator.load(QLocale.system(), ":/translations/recruitment_"):
        app.installTranslator(translator)

def verify_services():
    """Verify critical external services"""
    try:
        # Verify email service
        email_service = EmailService(
            smtp_server=config.SMTP_SERVER,
            smtp_port=config.SMTP_PORT,
            username=config.EMAIL_USERNAME,
            password=config.EMAIL_PASSWORD
        )
        email_service.verify_connection()
        
        # Verify security configuration
        if not config.SECRET_KEY or config.SECRET_KEY == "your-secret-key-here":
            logging.warning("Insecure secret key configuration detected")
        
        logging.info("External services verified successfully")
    except Exception as e:
        logging.error(f"Service verification failed: {str(e)}")
        QMessageBox.warning(
            None,
            "Service Warning",
            f"Some services may not be available:\n{str(e)}"
        )

def main():
    """Main application entry point"""
    # Configure logging
    configure_logging()
    
    # Create application instance
    app = QApplication(sys.argv)
    
    try:
        # Initialize and verify databases
        initialize_database()
        
        # Verify critical services
        verify_services()
        
        # Configure application settings
        configure_application(app)
        
        # Create and show authentication window
        auth_window = AuthWindow()
        auth_window.show()
        
        # Execute application
        sys.exit(app.exec())
        
    except Exception as e:
        logging.critical(f"Application startup failed: {str(e)}")
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Application failed to start:\n{str(e)}"
        )
        sys.exit(1)

if __name__ == "__main__":
    main()