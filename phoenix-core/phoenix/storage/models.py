"""SQLAlchemy database models"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class TestType(str, enum.Enum):
    """Test case type enumeration"""
    MANUAL = "manual"
    AUTOMATION = "automation"


class TestRisk(str, enum.Enum):
    """Test risk level enumeration"""
    SMOKE = "smoke"
    REGRESSION = "regression"
    EDGE = "edge"


class ExecutionStatus(str, enum.Enum):
    """Test execution status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class Project(Base):
    """Project model"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    test_cases = relationship("TestCase", back_populates="project", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"


class TestCase(Base):
    """Test case model (manual and automation)"""
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    test_type = Column(Enum(TestType), nullable=False, index=True)
    risk_level = Column(Enum(TestRisk), nullable=True, index=True)
    
    # Test content
    steps = Column(JSON, nullable=True)  # List of test steps
    expected_result = Column(Text, nullable=True)
    
    # Automation-specific
    script_path = Column(String(500), nullable=True)  # Path to generated Playwright script
    locators = Column(JSON, nullable=True)  # List of locators used
    
    # Metadata
    user_story = Column(Text, nullable=True)
    acceptance_criteria = Column(JSON, nullable=True)  # List of acceptance criteria
    tags = Column(JSON, nullable=True)  # List of tags
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="test_cases")
    executions = relationship("TestExecution", back_populates="test_case")

    def __repr__(self):
        return f"<TestCase(id={self.id}, name='{self.name}', type={self.test_type.value})>"


class Execution(Base):
    """Test execution run model"""
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    status = Column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False, index=True)
    
    # Execution details
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Results summary
    total_tests = Column(Integer, default=0, nullable=False)
    passed_tests = Column(Integer, default=0, nullable=False)
    failed_tests = Column(Integer, default=0, nullable=False)
    skipped_tests = Column(Integer, default=0, nullable=False)
    
    # Report
    report_path = Column(String(500), nullable=True)
    
    # Additional data
    execution_metadata = Column(JSON, nullable=True)  # Additional execution metadata
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="executions")
    test_executions = relationship("TestExecution", back_populates="execution", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Execution(id={self.id}, status={self.status.value}, project_id={self.project_id})>"


class TestExecution(Base):
    """Individual test case execution result"""
    __tablename__ = "test_executions"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True)
    
    status = Column(Enum(ExecutionStatus), nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Failure details
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    
    # Additional data
    logs = Column(JSON, nullable=True)  # List of log entries
    test_metadata = Column(JSON, nullable=True)  # Additional test execution metadata

    # Relationships
    execution = relationship("Execution", back_populates="test_executions")
    test_case = relationship("TestCase", back_populates="executions")

    def __repr__(self):
        return f"<TestExecution(id={self.id}, status={self.status.value}, test_case_id={self.test_case_id})>"


class Locator(Base):
    """Cached locator model"""
    __tablename__ = "locators"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    
    # Locator details
    element_name = Column(String(255), nullable=False)
    locator_strategy = Column(String(50), nullable=False)  # data-testid, role, text, css, xpath
    locator_value = Column(String(500), nullable=False)
    locator_string = Column(String(500), nullable=False)  # Full locator string for Playwright
    
    # Validation
    is_stable = Column(Boolean, default=True, nullable=False)
    last_validated_at = Column(DateTime, nullable=True)
    validation_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    
    # Context
    page_url = Column(String(1000), nullable=True)
    page_title = Column(String(500), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Locator(id={self.id}, element='{self.element_name}', strategy={self.locator_strategy})>"
