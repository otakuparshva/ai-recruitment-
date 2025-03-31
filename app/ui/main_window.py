from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.ui.candidate_dashboard import CandidateDashboard
from app.ui.recruiter_dashboard import RecruiterDashboard
from app.ui.admin_dashboard import AdminDashboard
from app.utils.config import config

class MainWindow(QMainWindow):
    def __init__(self, role: str, email: str):
        super().__init__()
        self.role = role
        self.email = email
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"{config.APP_NAME} - {self.role.capitalize()} Dashboard")
        self.setMinimumSize(1024, 768)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Sidebar
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar, stretch=1)
        
        # Main content area (stacked widgets)
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, stretch=4)
        
        # Initialize role-specific dashboard
        self.init_dashboard()
        
        # Add logout button to sidebar
        logout_btn = QPushButton("Logout")
        logout_btn.clicked.connect(self.logout)
        self.sidebar.layout().addWidget(logout_btn)
    
    def create_sidebar(self):
        sidebar = QWidget()
        sidebar.setStyleSheet("background-color: #f0f0f0;")
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # User info
        user_label = QLabel(f"Logged in as:\n{self.email}")
        user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_label.setStyleSheet("font-weight: bold; margin-bottom: 20px;")
        
        layout.addWidget(user_label)
        
        # Navigation buttons will be added by child classes
        sidebar.setLayout(layout)
        return sidebar
    
    def init_dashboard(self):
        if self.role == "candidate":
            self.dashboard = CandidateDashboard(self.email)
        elif self.role == "recruiter":
            self.dashboard = RecruiterDashboard(self.email)
        elif self.role == "admin":
            self.dashboard = AdminDashboard(self.email)
        
        self.stacked_widget.addWidget(self.dashboard)
        self.stacked_widget.setCurrentWidget(self.dashboard)
    
    def logout(self):
        from app.ui.auth_window import AuthWindow
        self.auth_window = AuthWindow()
        self.auth_window.show()
        self.close()