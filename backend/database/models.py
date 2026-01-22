from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, Float, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.database.database import Base

class TestResultStatus(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    IGNORED = "ignored"
    ASSUMPTION_FAILURE = "assumption_failure"


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) # e.g., "Submission for fingerpint X"
    status = Column(String, default="draft") # draft, analyzing, ready, published
    gms_version = Column(String, nullable=True) # e.g., "14_r3"
    lab_name = Column(String, nullable=True)
    target_fingerprint = Column(String, index=True, nullable=True) # Auto-grouping Key
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    test_runs = relationship("TestRun", back_populates="submission")

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
    build_version_sdk = Column(String)  # SDK version (e.g., "35")
    build_abis = Column(String)         # ABIs (e.g., "arm64-v8a,armeabi-v7a,armeabi")
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
    xml_modules_done = Column(Integer, default=0)   # From XML <Summary modules_done>
    xml_modules_total = Column(Integer, default=0)  # From XML <Summary modules_total>
    status = Column(String, default="pending") # pending, processing, completed, failed
    analysis_status = Column(String, default="pending") # pending, analyzing, completed, failed
    
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=True)
    submission = relationship("Submission", back_populates="test_runs")

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
    app_base_url = Column(String, default="http://localhost:8000")
    
    # LLM Provider Settings
    llm_provider = Column(String, default="openai")  # openai | internal | cambrian
    internal_llm_url = Column(String, nullable=True)  # e.g., http://localhost:11434/v1
    internal_llm_model = Column(String, default="llama3.1:8b")  # Model name for internal LLM
    
    # Cambrian LLM Settings
    cambrian_url = Column(String, default="https://api.cambrian.pegatroncorp.com")
    cambrian_token = Column(String, nullable=True)  # Encrypted API token
    cambrian_model = Column(String, default="LLAMA 3.3 70B")

class TestSuiteConfig(Base):
    """Configuration for Test Suites (CTS, VTS, etc.)"""
    __tablename__ = "test_suite_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True) # CTS, VTS, CTSonGSI
    display_name = Column(String) # CTS, CTS on GSI
    is_required = Column(Integer, default=1) # Boolean logic (1=True)
    match_rule = Column(String, default="Standard") # Standard, GSI
    sort_order = Column(Integer, default=0)
    description = Column(String, nullable=True)

