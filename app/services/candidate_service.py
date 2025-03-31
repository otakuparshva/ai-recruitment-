from sqlalchemy.exc import SQLAlchemyError
from app.database.session import db_session
from app.database.models import Application, Job, User, Interview, InterviewAnswer
from app.services.s3_service import S3Service
from app.services.ai_service import AIService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CandidateService:
    def __init__(self, email: str):
        """
        Initialize the CandidateService with the candidate's email.
        
        Args:
            email: The candidate's email address
        """
        self.email = email
        self.s3_service = S3Service()
        self.ai_service = AIService()
    
    def get_available_jobs(self) -> list[dict]:
        """
        Get all available (approved) jobs.
        
        Returns:
            List of dictionaries containing job details
        """
        try:
            jobs = db_session.query(Job).filter(Job.status == "approved").all()
            return [{
                'id': job.id,
                'title': job.title,
                'department': job.department,
                'location': job.location,
                'salary_min': job.salary_min,
                'salary_max': job.salary_max,
                'description': job.description,
                'skills': [skill.skill for skill in job.skills]
            } for job in jobs]
        except SQLAlchemyError as e:
            logger.error(f"Error fetching available jobs: {e}")
            return []
    
    def apply_for_job(self, job_id: int, resume_path: str) -> bool:
        """
        Apply for a job by submitting a resume.
        
        Args:
            job_id: The ID of the job to apply for
            resume_path: Path to the resume file
            
        Returns:
            True if application was successful, False otherwise
        """
        try:
            # Upload resume to S3
            success, s3_key = self.s3_service.upload_resume(resume_path, self.email)
            if not success:
                return False
            
            # Extract text from resume
            resume_text = self.ai_service.extract_text_from_file(resume_path)
            
            # Get job details
            job = db_session.query(Job).get(job_id)
            if not job:
                return False
            
            # Generate match score
            _, match_score = self.ai_service.generate_resume_summary(resume_text, job.description)
            
            # Get candidate
            candidate = db_session.query(User).filter(User.email == self.email).first()
            if not candidate:
                return False
            
            # Create application
            application = Application(
                job_id=job_id,
                candidate_id=candidate.id,
                resume_s3_key=s3_key,
                resume_text=resume_text[:2000],  # Store first 2000 chars
                match_score=match_score,
                status="applied",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db_session.add(application)
            db_session.commit()
            
            return True
        except SQLAlchemyError as e:
            db_session.rollback()
            logger.error(f"Database error applying for job: {e}")
            return False
        except Exception as e:
            logger.error(f"Error applying for job: {e}")
            return False
    
    def start_interview(self, job_id: int) -> list:
        """
        Start an interview for a specific job application.
        
        Args:
            job_id: The ID of the job to interview for
            
        Returns:
            List of interview questions or empty list if error occurs
        """
        try:
            application = db_session.query(Application).filter(
                Application.job_id == job_id,
                Application.candidate.has(email=self.email)
            ).first()
            
            if not application:
                return []
                
            job = db_session.query(Job).get(job_id)
            questions = self.ai_service.generate_interview_questions(
                job.description,
                application.resume_text
            )
            return questions
        except SQLAlchemyError as e:
            logger.error(f"Database error starting interview: {e}")
            return []
        except Exception as e:
            logger.error(f"Error starting interview: {e}")
            return []
    
    def submit_interview_results(self, job_id: int, results: dict) -> bool:
        """
        Save interview results to database.
        
        Args:
            job_id: The ID of the job interviewed for
            results: Dictionary containing interview results
            
        Returns:
            True if submission was successful, False otherwise
        """
        try:
            application = db_session.query(Application).filter(
                Application.job_id == job_id,
                Application.candidate.has(email=self.email)
            ).first()
            
            if not application:
                return False
                
            # Create interview record
            interview = Interview(
                application_id=application.id,
                score=results['score'],
                total_questions=results['total'],
                completed_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db_session.add(interview)
            db_session.flush()  # Get interview ID
            
            # Add answers
            for answer in results['answers']:
                interview_answer = InterviewAnswer(
                    interview_id=interview.id,
                    question=answer['question'],
                    answer=answer['answer'],
                    is_correct=answer['correct'],
                    difficulty=answer['difficulty'],
                    created_at=datetime.utcnow()
                )
                db_session.add(interview_answer)
            
            # Update application status
            application.status = "interviewed"
            application.updated_at = datetime.utcnow()
            
            db_session.commit()
            return True
        except SQLAlchemyError as e:
            db_session.rollback()
            logger.error(f"Error saving interview results: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving interview results: {e}")
            return False
        
    def get_my_applications(self) -> list[dict]:
        """
        Get all applications for the current candidate.
        
        Returns:
            List of dictionaries containing application details
        """
        try:
            candidate = db_session.query(User).filter(User.email == self.email).first()
            if not candidate:
                return []
                
            applications = db_session.query(Application).filter(
                Application.candidate_id == candidate.id
            ).all()
            
            return [{
                'job_id': app.job.id,
                'job_title': app.job.title,
                'department': app.job.department,
                'status': app.status,
                'applied_at': app.created_at.strftime("%Y-%m-%d"),
                'match_score': app.match_score,
                'interview_status': "Completed" if app.interview else "Pending",
                'interview_score': app.interview.score if app.interview else None
            } for app in applications]
        except SQLAlchemyError as e:
            logger.error(f"Error fetching applications: {e}")
            return []