import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String) # Admin, Underwriter, Reviewer, Compliance

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True)
    applicant_name = Column(String)
    risk_score = Column(Integer, default=0)
    status = Column(String, default="Pending") # Pending, Approved, Rejected, Escalated
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.case_id"))
    filename = Column(String)
    doc_type = Column(String) # Salary Slip, Bank Statement, ITR, Property Deed, Land Record, etc.
    file_path = Column(String)
    ela_image_url = Column(String, nullable=True)
    ela_overlay_url = Column(String, nullable=True)  # Hot-colormap composite overlay
    risk_score = Column(Integer, default=0)
    doc_hash = Column(String, nullable=True)  # Perceptual/difference hash for duplicate detection
    
    # Store JSON strings for structural analysis
    ocr_data = Column(Text, default="{}")
    font_anomalies = Column(Text, default="[]")
    metadata_anomalies = Column(Text, default="[]")
    
    case = relationship("Case", back_populates="documents")

class FraudPattern(Base):
    __tablename__ = "fraud_patterns"
    
    id = Column(Integer, primary_key=True, index=True)
    pattern_type = Column(String)  # hash, pan, employer, metadata
    pattern_value = Column(String, unique=True, index=True)
    severity = Column(String, default="HIGH")
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    action = Column(String)
    username = Column(String)
    notes = Column(Text, nullable=True)
