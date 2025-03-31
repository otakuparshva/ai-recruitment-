from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget, 
    QTextEdit, QPushButton, QLabel, QLineEdit, QFileDialog,
    QMessageBox, QComboBox, QSpinBox, QTextBrowser
)
from PyQt6.QtCore import Qt
from app.services.recruiter_service import RecruiterService
from app.services.ai_service import AIService

class RecruiterDashboard(QWidget):
    def __init__(self, email: str):
        super().__init__()
        self.email = email
        self.recruiter_service = RecruiterService(email)
        self.ai_service = AIService()
        self.current_job_id = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Tab widget for different sections
        self.tabs = QTabWidget()
        
        # Post Jobs tab
        self.post_job_tab = QWidget()
        self.init_post_job_tab()
        
        # Review Candidates tab
        self.review_tab = QWidget()
        self.init_review_tab()
        
        # ATS tab
        self.ats_tab = QWidget()
        self.init_ats_tab()
        
        self.tabs.addTab(self.post_job_tab, "Post Jobs")
        self.tabs.addTab(self.review_tab, "Review Candidates")
        self.tabs.addTab(self.ats_tab, "ATS")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def init_post_job_tab(self):
        layout = QVBoxLayout()
        
        # Job Title
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Job Title:"))
        self.job_title = QLineEdit()
        title_layout.addWidget(self.job_title)
        
        # Department
        dept_layout = QHBoxLayout()
        dept_layout.addWidget(QLabel("Department:"))
        self.department = QLineEdit()
        dept_layout.addWidget(self.department)
        
        # Location
        loc_layout = QHBoxLayout()
        loc_layout.addWidget(QLabel("Location:"))
        self.location = QLineEdit()
        loc_layout.addWidget(self.location)
        
        # Skills
        skills_layout = QVBoxLayout()
        skills_layout.addWidget(QLabel("Required Skills (one per line):"))
        self.skills = QTextEdit()
        self.skills.setMaximumHeight(100)
        skills_layout.addWidget(self.skills)
        
        # Salary Range
        salary_layout = QHBoxLayout()
        salary_layout.addWidget(QLabel("Salary Range:"))
        self.salary_min = QSpinBox()
        self.salary_min.setMaximum(1000000)
        self.salary_min.setValue(50000)
        self.salary_max = QSpinBox()
        self.salary_max.setMaximum(1000000)
        self.salary_max.setValue(100000)
        salary_layout.addWidget(QLabel("Min:"))
        salary_layout.addWidget(self.salary_min)
        salary_layout.addWidget(QLabel("Max:"))
        salary_layout.addWidget(self.salary_max)
        
        # Generate Description Button
        gen_desc_btn = QPushButton("Generate Description with AI")
        gen_desc_btn.clicked.connect(self.generate_job_description)
        
        # Job Description
        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Job Description:"))
        self.job_desc = QTextEdit()
        desc_layout.addWidget(self.job_desc)
        
        # Post Job Button
        post_btn = QPushButton("Post Job")
        post_btn.clicked.connect(self.post_job)
        
        # Add all to main layout
        layout.addLayout(title_layout)
        layout.addLayout(dept_layout)
        layout.addLayout(loc_layout)
        layout.addLayout(skills_layout)
        layout.addLayout(salary_layout)
        layout.addWidget(gen_desc_btn)
        layout.addLayout(desc_layout)
        layout.addWidget(post_btn)
        
        self.post_job_tab.setLayout(layout)
    
    def init_review_tab(self):
        layout = QVBoxLayout()
        
        # Job selection
        job_select_layout = QHBoxLayout()
        job_select_layout.addWidget(QLabel("Select Job:"))
        self.job_combo = QComboBox()
        job_select_layout.addWidget(self.job_combo, stretch=1)
        
        # Candidate list
        self.candidate_list = QListWidget()
        self.candidate_list.itemClicked.connect(self.show_candidate_details)
        
        # Candidate details
        self.candidate_details = QTextBrowser()
        
        # Action buttons
        button_layout = QHBoxLayout()
        self.accept_btn = QPushButton("Accept Candidate")
        self.accept_btn.clicked.connect(self.accept_candidate)
        self.reject_btn = QPushButton("Reject Candidate")
        self.reject_btn.clicked.connect(self.reject_candidate)
        self.ai_summary_btn = QPushButton("Generate AI Summary")
        self.ai_summary_btn.clicked.connect(self.generate_ai_summary)
        
        button_layout.addWidget(self.accept_btn)
        button_layout.addWidget(self.reject_btn)
        button_layout.addWidget(self.ai_summary_btn)
        
        # Split view
        split_layout = QHBoxLayout()
        split_layout.addWidget(self.candidate_list, 1)
        split_layout.addWidget(self.candidate_details, 2)
        
        # Add all to main layout
        layout.addLayout(job_select_layout)
        layout.addLayout(split_layout)
        layout.addLayout(button_layout)
        
        self.review_tab.setLayout(layout)
        
        # Load jobs
        self.load_jobs_for_review()
    
    def init_ats_tab(self):
        # Similar implementation for ATS tab
        pass
    
    def load_jobs_for_review(self):
        jobs = self.recruiter_service.get_my_jobs()
        self.job_combo.clear()
        for job in jobs:
            self.job_combo.addItem(job['title'], job['id'])
    
    def generate_job_description(self):
        job_title = self.job_title.text().strip()
        department = self.department.text().strip()
        skills = self.skills.toPlainText().strip().split('\n')
        
        if not job_title or not department or not skills:
            QMessageBox.warning(self, "Warning", "Please fill in job title, department, and skills")
            return
        
        try:
            description = self.ai_service.generate_job_description(
                job_title, department, skills
            )
            self.job_desc.setPlainText(description)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate description: {str(e)}")
    
    def post_job(self):
        job_data = {
            'title': self.job_title.text().strip(),
            'department': self.department.text().strip(),
            'location': self.location.text().strip(),
            'description': self.job_desc.toPlainText().strip(),
            'skills': [s.strip() for s in self.skills.toPlainText().strip().split('\n') if s.strip()],
            'salary_min': self.salary_min.value(),
            'salary_max': self.salary_max.value()
        }
        
        if not job_data['title'] or not job_data['description']:
            QMessageBox.warning(self, "Warning", "Title and description are required")
            return
        
        if job_data['salary_min'] > job_data['salary_max']:
            QMessageBox.warning(self, "Warning", "Minimum salary cannot be greater than maximum")
            return
        
        success, message = self.recruiter_service.post_job(job_data)
        if success:
            QMessageBox.information(self, "Success", "Job posted successfully!")
            self.clear_job_form()
        else:
            QMessageBox.critical(self, "Error", message)
    
    def clear_job_form(self):
        self.job_title.clear()
        self.department.clear()
        self.location.clear()
        self.skills.clear()
        self.salary_min.setValue(50000)
        self.salary_max.setValue(100000)
        self.job_desc.clear()
    
    def show_candidate_details(self, item):
        job_id = self.job_combo.currentData()
        candidate_email = item.text()
        
        candidate = self.recruiter_service.get_candidate_details(job_id, candidate_email)
        if not candidate:
            return
        
        details = f"""
        <h2>{candidate['name']}</h2>
        <p><b>Email:</b> {candidate['email']}</p>
        <p><b>Match Score:</b> {candidate['match_score']}%</p>
        <h3>Resume Summary:</h3>
        <p>{candidate['resume_summary']}</p>
        """
        self.candidate_details.setHtml(details)
    
    def accept_candidate(self):
        job_id = self.job_combo.currentData()
        candidate_item = self.candidate_list.currentItem()
        
        if not candidate_item:
            return
            
        candidate_email = candidate_item.text()
        success = self.recruiter_service.accept_candidate(job_id, candidate_email)
        
        if success:
            QMessageBox.information(self, "Success", "Candidate accepted and notified")
        else:
            QMessageBox.critical(self, "Error", "Failed to accept candidate")
    
    def reject_candidate(self):
        job_id = self.job_combo.currentData()
        candidate_item = self.candidate_list.currentItem()
        
        if not candidate_item:
            return
            
        candidate_email = candidate_item.text()
        success = self.recruiter_service.reject_candidate(job_id, candidate_email)
        
        if success:
            QMessageBox.information(self, "Success", "Candidate rejected and notified")
        else:
            QMessageBox.critical(self, "Error", "Failed to reject candidate")
    
    def generate_ai_summary(self):
        job_id = self.job_combo.currentData()
        candidate_item = self.candidate_list.currentItem()
        
        if not candidate_item:
            return
            
        candidate_email = candidate_item.text()
        
        try:
            summary = self.recruiter_service.generate_ai_summary(job_id, candidate_email)
            self.candidate_details.append("\n\n<b>AI Analysis:</b>")
            self.candidate_details.append(summary)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate AI summary: {str(e)}")
