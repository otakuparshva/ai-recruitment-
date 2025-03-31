from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QPushButton, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.services.ai_service import AIService

class InterviewWindow(QWidget):
    interview_completed = pyqtSignal(dict)  # emits results when done
    
    def __init__(self, questions: list, job_title: str):
        super().__init__()
        self.questions = questions
        self.job_title = job_title
        self.current_question = 0
        self.answers = []
        self.score = 0
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"Interview for {self.job_title}")
        self.setFixedSize(600, 400)
        
        self.layout = QVBoxLayout()
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setMaximum(len(self.questions))
        self.update_progress()
        
        # Question label
        self.question_label = QLabel()
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        # Options group
        self.options_group = QButtonGroup()
        self.option_widgets = []
        for i in range(4):
            option = QRadioButton()
            option.setStyleSheet("font-size: 12px;")
            self.option_widgets.append(option)
            self.options_group.addButton(option, i)
        
        # Submit button
        self.submit_btn = QPushButton("Submit Answer")
        self.submit_btn.clicked.connect(self.submit_answer)
        
        # Add widgets to layout
        self.layout.addWidget(self.progress)
        self.layout.addWidget(self.question_label)
        for option in self.option_widgets:
            self.layout.addWidget(option)
        self.layout.addStretch()
        self.layout.addWidget(self.submit_btn)
        
        self.setLayout(self.layout)
        self.show_question()
    
    def show_question(self):
        if self.current_question >= len(self.questions):
            self.complete_interview()
            return
            
        question = self.questions[self.current_question]
        self.question_label.setText(question['question'])
        
        for i, option in enumerate(question['options']):
            self.option_widgets[i].setText(option)
            self.option_widgets[i].setVisible(True)
        
        # Hide unused options
        for i in range(len(question['options']), 4):
            self.option_widgets[i].setVisible(False)
        
        self.options_group.setExclusive(False)
        for button in self.option_widgets:
            button.setChecked(False)
        self.options_group.setExclusive(True)
    
    def update_progress(self):
        self.progress.setValue(self.current_question + 1)
        self.progress.setFormat(f"Question {self.current_question + 1} of {len(self.questions)}")
    
    def submit_answer(self):
        selected = self.options_group.checkedId()
        if selected == -1:
            QMessageBox.warning(self, "Warning", "Please select an answer")
            return
            
        question = self.questions[self.current_question]
        is_correct = (selected == question['correct'])
        
        if is_correct:
            self.score += 1
        
        self.answers.append({
            'question': question['question'],
            'answer': question['options'][selected],
            'correct': is_correct,
            'difficulty': question.get('difficulty', 1.0)
        })
        
        self.current_question += 1
        self.update_progress()
        
        if self.current_question < len(self.questions):
            self.show_question()
        else:
            self.complete_interview()
    
    def complete_interview(self):
        results = {
            'score': self.score,
            'total': len(self.questions),
            'answers': self.answers
        }
        self.interview_completed.emit(results)
        self.close()