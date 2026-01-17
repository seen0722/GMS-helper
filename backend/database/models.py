from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.database.database import Base

class TestResultStatus(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    IGNORED = "ignored"
    ASSUMPTION_FAILURE = "assumption_failure"

class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    test_suite_name = Column(String, index=True) # e.g., CTS, VTS
    device_fingerprint = Column(String)
    build_id = Column(String)
    build_product = Column(String)
    build_model = Column(String)
    build_type = Column(String)
    security_patch = Column(String)
    android_version = Column(String)
    build_version_incremental = Column(String)
    suite_version = Column(String)
    suite_plan = Column(String)
    suite_build_number = Column(String)
    host_name = Column(String)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    start_display = Column(String)
    end_display = Column(String)
    total_tests = Column(Integer, default=0)
    passed_tests = Column(Integer, default=0)
    failed_tests = Column(Integer, default=0)
    ignored_tests = Column(Integer, default=0)
    total_modules = Column(Integer, default=0)
    passed_modules = Column(Integer, default=0)
    failed_modules = Column(Integer, default=0)
    status = Column(String, default="pending") # pending, processing, completed, failed
    analysis_status = Column(String, default="pending") # pending, analyzing, completed, failed
    
    test_cases = relationship("TestCase", back_populates="test_run", cascade="all, delete-orphan")

class TestCase(Base):
    # NOTE: This table ONLY stores failed test cases to save space and improve performance.
    # Passing test cases are counted in TestRun stats but not stored individually.
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    test_run_id = Column(Integer, ForeignKey("test_runs.id"))
    module_name = Column(String, index=True)
    module_abi = Column(String)
    class_name = Column(String, index=True)
    method_name = Column(String, index=True)
    status = Column(String) # stored as string to be flexible, but logically TestResultStatus
    stack_trace = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    test_run = relationship("TestRun", back_populates="test_cases")
    failure_analysis = relationship("FailureAnalysis", uselist=False, back_populates="test_case", cascade="all, delete-orphan")

class FailureAnalysis(Base):
    __tablename__ = "failure_analysis"

    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"))
    cluster_id = Column(Integer, ForeignKey("failure_clusters.id"), nullable=True)
    root_cause = Column(Text, nullable=True)
    suggested_solution = Column(Text, nullable=True)
    ai_analysis_timestamp = Column(DateTime, default=datetime.utcnow)

    test_case = relationship("TestCase", back_populates="failure_analysis")
    cluster = relationship("FailureCluster", back_populates="analyses")

class FailureCluster(Base):
    __tablename__ = "failure_clusters"
    
    id = Column(Integer, primary_key=True, index=True)
    signature = Column(Text, unique=True) # A hash or representative string of the stack trace
    description = Column(String)
    common_root_cause = Column(Text, nullable=True)
    common_solution = Column(Text, nullable=True)
    
    analyses = relationship("FailureAnalysis", back_populates="cluster")
    
    # AI Analysis Fields
    ai_summary = Column(Text, nullable=True)
    severity = Column(String, default="Medium") # High, Medium, Low
    category = Column(String, nullable=True) # e.g., System, Driver, App
    confidence_score = Column(Integer, default=0) # 1-5
    suggested_assignment = Column(String, nullable=True) # e.g., Audio Team
    redmine_issue_id = Column(Integer, nullable=True) # Linked Redmine Issue ID

class Settings(Base):
    """Store application settings with encrypted values."""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    openai_api_key = Column(String, nullable=True)
    redmine_url = Column(String, nullable=True)
    redmine_api_key = Column(String, nullable=True)
    
    # LLM Provider Settings
    llm_provider = Column(String, default="openai")  # openai | internal | cambrian
    internal_llm_url = Column(String, nullable=True)  # e.g., http://localhost:11434/v1
    internal_llm_model = Column(String, default="llama3.1:8b")  # Model name for internal LLM
    
    # Cambrian LLM Settings
    cambrian_url = Column(String, default="https://api.cambrian.pegatroncorp.com")
    cambrian_token = Column(String, nullable=True)  # Encrypted API token
    cambrian_model = Column(String, default="LLAMA 3.3 70B")
