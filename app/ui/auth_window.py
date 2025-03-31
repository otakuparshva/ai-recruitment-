from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTabWidget, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.services.auth_service import AuthService


from app.utils.config import config

class AuthWindow(QWidget):
    login_success = pyqtSignal(str)  # role
    
    def __init__(self):
        super().__init__()
        self.auth_service = AuthService()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"{config.APP_NAME} - Authentication")
        self.setFixedSize(400, 400)
        
        # Main layout
        layout = QVBoxLayout()
        
        # Tab widget for login/register
        self.tabs = QTabWidget()
        
        # Login tab
        self.login_tab = QWidget()
        self.init_login_tab()
        
        # Register tab
        self.register_tab = QWidget()
        self.init_register_tab()
        
        self.tabs.addTab(self.login_tab, "Login")
        self.tabs.addTab(self.register_tab, "Register")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def init_login_tab(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Email
        email_label = QLabel("Email:")
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("Enter your email")
        
        # Password
        password_label = QLabel("Password:")
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Enter your password")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.handle_login)
        
        # Add widgets to layout
        layout.addWidget(email_label)
        layout.addWidget(self.login_email)
        layout.addWidget(password_label)
        layout.addWidget(self.login_password)
        layout.addWidget(login_btn)
        
        self.login_tab.setLayout(layout)
    
    def init_register_tab(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Email
        email_label = QLabel("Email:")
        self.register_email = QLineEdit()
        self.register_email.setPlaceholderText("Enter your email")
        
        # Password
        password_label = QLabel("Password:")
        self.register_password = QLineEdit()
        self.register_password.setPlaceholderText("Enter your password")
        self.register_password.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Confirm Password
        confirm_password_label = QLabel("Confirm Password:")
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("Confirm your password")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Role selection
        role_label = QLabel("Role:")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["candidate", "recruiter"])
        
        # Register button
        register_btn = QPushButton("Register")
        register_btn.clicked.connect(self.handle_register)
        
        # Add widgets to layout
        layout.addWidget(email_label)
        layout.addWidget(self.register_email)
        layout.addWidget(password_label)
        layout.addWidget(self.register_password)
        layout.addWidget(confirm_password_label)
        layout.addWidget(self.confirm_password)
        layout.addWidget(role_label)
        layout.addWidget(self.role_combo)
        layout.addWidget(register_btn)
        
        self.register_tab.setLayout(layout)
    
    def handle_login(self):
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()
        
        if not email or not password:
            self.show_error("Please enter both email and password")
            return
        