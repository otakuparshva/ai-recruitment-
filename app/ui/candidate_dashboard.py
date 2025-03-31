from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QTextEdit, QFileDialog,
    QListWidget, QStackedWidget
)
from PyQt6.QtCore import Qt
from app.services.candidate_service import CandidateService
from app.ui.main_window import MainWindow

class CandidateDashboard(QWidget):
    def __init__(self, email: str):
        super().__init__()
        self.email = email
        self.candidate_service = CandidateService(email)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Tab widget for different sections
        self.tabs = QTabWidget()
        
        # Available Jobs tab
        self.jobs_tab = QWidget()
        self.init_jobs_tab()
        
        # My Applications tab
        self.applications_tab = QWidget()
        self.init_applications_tab()
        
        # Interviews tab
        self.interviews_tab = QWidget()
        self.init_interviews_tab()
        
        self.tabs.addTab(self.jobs_tab, "Available Jobs")
        self.tabs.addTab(self.applications_tab, "My Applications")
        self.tabs.addTab(self.interviews_tab, "Interviews")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def init_jobs_tab(self):
        layout = QVBoxLayout()
        
        # Job list
        self.job_list = QListWidget()
        self.job_list.itemClicked.connect(self.show_job_details)
        
        # Job details
        self.job_details = QTextEdit()
        self.job_details.setReadOnly(True)
        
        # Apply section
        self.resume_upload = QPushButton("Upload Resume")
        self.resume_upload.clicked.connect(self.upload_resume)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply_for_job)
        
        # Layout
        split_layout = QHBoxLayout()
        split_layout.addWidget(self.job_list, 1)
        split_layout.addWidget(self.job_details, 2)
        
        layout.addLayout(split_layout)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.resume_upload)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
        
        self.jobs_tab.setLayout(layout)
        
        # Load jobs
        self.load_jobs()
    
    def init_applications_tab(self):
        # Similar implementation for applications tab
        pass
    
    def init_interviews_tab(self):
        # Similar implementation for interviews tab
        pass
    
    def load_jobs(self):
        jobs = self.candidate_service.get_available_jobs()
        self.job_list.clear()
        for job in jobs:
            self.job_list.addItem(f"{job['title']} - {job['department']}")
    
    def show_job_details(self, item):
        job_title = item.text().split(" - ")[0]
        job = self.candidate_service.get_job_details(job_title)
        
        details = f"""
        <h2>{job['title']}</h2>
        <p><b>Department:</b> {job['department']}</p>
        <p><b>Location:</b> {job['location']}</p>
        <p><b>Salary Range:</b> ${job['salary_min']:,} - ${job['salary_max']:,}</p>
        <h3>Description:</h3>
        <p>{job['description']}</p>
        <h3>Required Skills:</h3>
        <ul>
        {"".join(f"<li>{skill}</li>" for skill in job['skills'])}
        </ul>
        """
        self.job_details.setHtml(details)
    
    def upload_resume(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select Resume", "", 
            "Documents (*.pdf *.docx);;Images (*.png *.jpg)"
        )
        
        if file_path:
            self.current_resume_path = file_path
    
    def apply_for_job(self):
        selected_item = self.job_list.currentItem()
        if not selected_item:
            return
            
        if not hasattr(self, 'current_resume_path'):
            return
            
        job_title = selected_item.text().split(" - ")[0]
        success = self.candidate_service.apply_for_job(job_title, self.current_resume_path)
        
        if success:
            # Show success message
            pass
        else:
            # Show error message
            pass

    def init_interviews_tab(self):
        layout = QVBoxLayout()
        
        # Pending interviews list
        self.interview_list = QListWidget()
        self.interview_list.itemClicked.connect(self.select_interview)
        
        # Start interview button
        self.start_interview_btn = QPushButton("Start Interview")
        self.start_interview_btn.clicked.connect(self.start_interview)
        self.start_interview_btn.setEnabled(False)
        
        # Interview results
        self.results_label = QLabel()
        self.results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_label.setStyleSheet("font-size: 14px;")
        
        layout.addWidget(QLabel("Pending Interviews:"))
        layout.addWidget(self.interview_list)
        layout.addWidget(self.start_interview_btn)
        layout.addWidget(self.results_label)
        
        self.interviews_tab.setLayout(layout)
        self.load_interviews()
    
    def load_interviews(self):
        interviews = self.candidate_service.get_pending_interviews()
        self.interview_list.clear()
        
        for interview in interviews:
            item = QListWidgetItem(f"{interview['job_title']} - {interview['department']}")
            item.setData(Qt.ItemDataRole.UserRole, interview['job_id'])
            self.interview_list.addItem(item)
    
    def select_interview(self, item):
        self.selected_job_id = item.data(Qt.ItemDataRole.UserRole)
        self.start_interview_btn.setEnabled(True)
    
    def start_interview(self):
        if not hasattr(self, 'selected_job_id'):
            return
            
        questions = self.candidate_service.start_interview(self.selected_job_id)
        if not questions:
            QMessageBox.warning(self, "Error", "Could not generate interview questions")
            return
            
        self.interview_window = InterviewWindow(questions, self.interview_list.currentItem().text())
        self.interview_window.interview_completed.connect(self.interview_finished)
        self.interview_window.show()
    
    def interview_finished(self, results):
        success = self.candidate_service.submit_interview_results(
            self.selected_job_id, results
        )
        
        if success:
            score_percent = (results['score'] / results['total']) * 100
            self.results_label.setText(
                f"Interview completed! Score: {results['score']}/{results['total']} ({score_percent:.1f}%)"
            )
            self.load_interviews()
        else:
            QMessageBox.critical(self, "Error", "Failed to save interview results")