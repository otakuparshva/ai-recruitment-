from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt
from app.services.admin_service import AdminService

class AdminDashboard(QWidget):
    def __init__(self, email: str):
        super().__init__()
        self.email = email
        self.admin_service = AdminService(email)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Tab widget for different sections
        self.tabs = QTabWidget()
        
        # User Management tab
        self.users_tab = QWidget()
        self.init_users_tab()
        
        # Job Approval tab
        self.jobs_tab = QWidget()
        self.init_jobs_tab()
        
        # System Monitoring tab
        self.monitor_tab = QWidget()
        self.init_monitor_tab()
        
        self.tabs.addTab(self.users_tab, "User Management")
        self.tabs.addTab(self.jobs_tab, "Job Approvals")
        self.tabs.addTab(self.monitor_tab, "System Monitor")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def init_users_tab(self):
        layout = QVBoxLayout()
        
        # User table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(5)
        self.user_table.setHorizontalHeaderLabels(["ID", "Email", "Role", "Status", "Actions"])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Users")
        refresh_btn.clicked.connect(self.load_users)
        
        layout.addWidget(self.user_table)
        layout.addWidget(refresh_btn)
        
        self.users_tab.setLayout(layout)
        self.load_users()
    
    def init_jobs_tab(self):
        layout = QVBoxLayout()
        
        # Jobs table
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(6)
        self.jobs_table.setHorizontalHeaderLabels(["ID", "Title", "Department", "Status", "Poster", "Actions"])
        self.jobs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Jobs")
        refresh_btn.clicked.connect(self.load_jobs)
        
        layout.addWidget(self.jobs_table)
        layout.addWidget(refresh_btn)
        
        self.jobs_tab.setLayout(layout)
        self.load_jobs()
    
    def init_monitor_tab(self):
        layout = QVBoxLayout()
        
        # System stats
        stats = self.admin_service.get_system_stats()
        
        # Active users
        active_users_label = QLabel(f"Active Users: {stats['active_users']}")
        
        # Pending jobs
        pending_jobs_label = QLabel(f"Pending Jobs: {stats['pending_jobs']}")
        
        # Storage usage
        storage_label = QLabel(f"Storage Used: {stats['storage_used']} MB")
        
        # Recent activity
        activity_label = QLabel("Recent Activity:")
        self.activity_list = QTableWidget()
        self.activity_list.setColumnCount(3)
        self.activity_list.setHorizontalHeaderLabels(["Timestamp", "User", "Action"])
        self.activity_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Add recent activities
        self.activity_list.setRowCount(len(stats['recent_activity']))
        for i, activity in enumerate(stats['recent_activity']):
            self.activity_list.setItem(i, 0, QTableWidgetItem(activity['timestamp']))
            self.activity_list.setItem(i, 1, QTableWidgetItem(activity['user']))
            self.activity_list.setItem(i, 2, QTableWidgetItem(activity['action']))
        
        layout.addWidget(active_users_label)
        layout.addWidget(pending_jobs_label)
        layout.addWidget(storage_label)
        layout.addWidget(activity_label)
        layout.addWidget(self.activity_list)
        
        self.monitor_tab.setLayout(layout)
    
    def load_users(self):
        users = self.admin_service.get_all_users()
        self.user_table.setRowCount(len(users))
        
        for i, user in enumerate(users):
            self.user_table.setItem(i, 0, QTableWidgetItem(str(user['id'])))
            self.user_table.setItem(i, 1, QTableWidgetItem(user['email']))
            self.user_table.setItem(i, 2, QTableWidgetItem(user['role']))
            
            status_item = QTableWidgetItem("Active" if user['is_active'] else "Inactive")
            status_item.setFlags(status_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.user_table.setItem(i, 3, status_item)
            
            # Add action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout()
            
            toggle_btn = QPushButton("Toggle Status")
            toggle_btn.clicked.connect(lambda _, u=user: self.toggle_user_status(u['id']))
            
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda _, u=user: self.delete_user(u['id']))
            
            action_layout.addWidget(toggle_btn)
            action_layout.addWidget(delete_btn)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            action_widget.setLayout(action_layout)
            self.user_table.setCellWidget(i, 4, action_widget)
    
    def load_jobs(self):
        jobs = self.admin_service.get_pending_jobs()
        self.jobs_table.setRowCount(len(jobs))
        
        for i, job in enumerate(jobs):
            self.jobs_table.setItem(i, 0, QTableWidgetItem(str(job['id'])))
            self.jobs_table.setItem(i, 1, QTableWidgetItem(job['title']))
            self.jobs_table.setItem(i, 2, QTableWidgetItem(job['department']))
            self.jobs_table.setItem(i, 3, QTableWidgetItem(job['status']))
            self.jobs_table.setItem(i, 4, QTableWidgetItem(job['poster_email']))
            
            # Add action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout()
            
            approve_btn = QPushButton("Approve")
            approve_btn.clicked.connect(lambda _, j=job: self.approve_job(j['id']))
            
            reject_btn = QPushButton("Reject")
            reject_btn.clicked.connect(lambda _, j=job: self.reject_job(j['id']))
            
            action_layout.addWidget(approve_btn)
            action_layout.addWidget(reject_btn)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            action_widget.setLayout(action_layout)
            self.jobs_table.setCellWidget(i, 5, action_widget)
    
    def toggle_user_status(self, user_id: int):
        success, message = self.admin_service.toggle_user_status(user_id)
        if success:
            QMessageBox.information(self, "Success", message)
            self.load_users()
        else:
            QMessageBox.critical(self, "Error", message)
    
    def delete_user(self, user_id: int):
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this user?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            success, message = self.admin_service.delete_user(user_id)
            if success:
                QMessageBox.information(self, "Success", message)
                self.load_users()
            else:
                QMessageBox.critical(self, "Error", message)
    
    def approve_job(self, job_id: int):
        success, message = self.admin_service.approve_job(job_id)
        if success:
            QMessageBox.information(self, "Success", message)
            self.load_jobs()
        else:
            QMessageBox.critical(self, "Error", message)
    
    def reject_job(self, job_id: int):
        success, message = self.admin_service.reject_job(job_id)
        if success:
            QMessageBox.information(self, "Success", message)
            self.load_jobs()
        else:
            QMessageBox.critical(self, "Error", message)