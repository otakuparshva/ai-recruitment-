from sqlalchemy.exc import SQLAlchemyError
from app.database.session import db_session
from app.database.models import Job, User, Application, JobSkill
from app.services.email_service import EmailService
from app.services.ai_service import AIService
from datetime import datetime
import uuid

class RecruiterService:
    def __init__(self, email: str):
        self.email = email
        self.ai_service = AIService()
        self.email_service = EmailService()
    
    def post_job(self, job_data: dict) -> tuple[bool, str]:
        try:
            # Get recruiter user
            recruiter = db_session.query(User).filter(User.email == self.email).first()
            if not recruiter:
                return False, "Recruiter not found"
            
            # Create new job
            new_job = Job(
                title=job_data['title'],
                department=job_data['department'],
                location=job_data['location'],
                description=job_data['description'],
                salary_min=job_data['salary_min'],
                salary_max=job_data['salary_max'],
                creator_id=recruiter.id,
                status="pending"  # Needs admin approval
            )
            
            db_session.add(new_job)
            db_session.flush()  # To get the job ID
            
            # Add skills
            for skill in job_data['skills']:
                job_skill = JobSkill(
                    job_id=new_job.id,
                    skill=skill.strip()
                )
                db_session.add(job_skill)
            
            db_session.commit()
            return True, "Job posted successfully"
        except SQLAlchemyError as e:
            db_session.rollback()
            return False, f"Database error: {str(e)}"
        except Exception as e:
            db_session.rollback()
            return False, f"Error posting job: {str(e)}"
    
    def get_my_jobs(self) -> list[dict]:
        recruiter = db_session.query(User).filter(User.email == self.email).first()
        if not recruiter:
            return []
            
        jobs = db_session.query(Job).filter(Job.creator_id == recruiter.id).all()
        return [{
            'id': job.id,
            'title': job.title,
            'department': job.department,
            'location': job.location,
            'status': job.status,
            'created_at': job.created_at.strftime("%Y-%m-%d")
        } for job in jobs]
    
    def get_job_candidates(self, job_id: int) -> list[dict]:
        applications = db_session.query(Application).filter(Application.job_id == job_id).all()
        return [{
            'email': app.candidate.email,
            'name': f"{app.candidate.first_name} {app.candidate.last_name}",
            'match_score': app.match_score,
            'status': app.status,
            'applied_at': app.created_at.strftime("%Y-%m-%d")
        } for app in applications]
    
    def get_candidate_details(self, job_id: int, candidate_email: str) -> dict:
        application = db_session.query(Application).join(User).filter(
            Application.job_id == job_id,
            User.email == candidate_email
        ).first()
        
        if not application:
            return None
            
        return {
            'email': application.candidate.email,
            'name': f"{application.candidate.first_name} {application.candidate.last_name}",
            'match_score': application.match_score,
            'resume_summary': application.resume_summary,
            'status': application.status
        }
    
    def accept_candidate(self, job_id: int, candidate_email: str) -> bool:
        try:
            application = db_session.query(Application).join(User).filter(
                Application.job_id == job_id,
                User.email == candidate_email
            ).first()
            
            if not application:
                return False
                
            application.status = "accepted"
            db_session.commit()
            
            # Send email notification
            job = db_session.query(Job).get(job_id)
            subject = f"Congratulations! You've been selected for {job.title}"
            body = f"Dear {application.candidate.first_name},\n\n" \
                   f"We're pleased to inform you that you've been selected for the {job.title} position.\n\n" \
                   "Best regards,\nRecruitment Team"
            
            self.email_service.send_email(
                recipient=candidate_email,
                subject=subject,
                body=body
            )
            
            return True
        except Exception as e:
            db_session.rollback()
            return False
    
    def reject_candidate(self, job_id: int, candidate_email: str) -> bool:
        try:
            application = db_session.query(Application).join(User).filter(
                Application.job_id == job_id,
                User.email == candidate_email
            ).first()
            
            if not application:
                return False
                
            application.status = "rejected"
            db_session.commit()
            
            # Send email notification
            job = db_session.query(Job).get(job_id)
            subject = f"Regarding your application for {job.title}"
            body = f"Dear {application.candidate.first_name},\n\n" \
                   f"Thank you for applying for the {job.title} position. " \
                   "After careful consideration, we've decided to move forward with other candidates.\n\n" \
                   "Best regards,\nRecruitment Team"
            
            self.email_service.send_email(
                recipient=candidate_email,
                subject=subject,
                body=body
            )
            
            return True
        except Exception as e:
            db_session.rollback()
            return False
    
    def generate_ai_summary(self, job_id: int, candidate_email: str) -> str:
        application = db_session.query(Application).join(User).filter(
            Application.job_id == job_id,
            User.email == candidate_email
        ).first()
        
        if not application:
            return "Candidate not found"
            
        job = db_session.query(Job).get(job_id)
        
        summary = self.ai_service.generate_resume_summary(
            resume_text=application.resume_text,
            job_description=job.description
        )
        
        return summary