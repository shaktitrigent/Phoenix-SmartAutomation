"""Phoenix SDK Client - Main entry point"""

from typing import Optional, List, Dict, Any
from phoenix.sdk.config import PhoenixConfig
from phoenix.storage.database import Database
from phoenix.generators.manual import ManualTestGenerator
from phoenix.generators.automation import AutomationTestGenerator
from phoenix.execution.runner import TestRunner
from phoenix.reporting.html_reporter import HTMLReporter
from phoenix.storage.models import (
    Project,
    TestCase,
    Execution,
    TestExecution,
    TestType,
    ExecutionStatus,
)
from phoenix.sdk.intelligence_client import IntelligenceClient
from datetime import datetime, timezone


class PhoenixClient:
    """
    Main Phoenix SDK client.

    Provides high-level API for test generation and execution.
    """

    def __init__(self, config: Optional[PhoenixConfig] = None, config_path: Optional[str] = None):
        """
        Initialize Phoenix client.

        Args:
            config: PhoenixConfig instance. If None, loads from file or environment.
            config_path: Path to config YAML file. If None, looks for config.yaml or uses env vars.
        """
        self.config = config or PhoenixConfig.load(config_path)
        self._project_context: Optional[str] = None

        # Initialize components
        self._database = Database(self.config)
        self._database.create_tables()  # Ensure tables exist

        self._intelligence_client = IntelligenceClient(self.config)

        self._manual_generator = ManualTestGenerator(
            output_dir=self.config.project.manual_output_dir
        )
        self._automation_generator = AutomationTestGenerator(
            output_dir=self.config.project.test_output_dir
        )

        self._test_runner = TestRunner(test_output_dir=self.config.project.test_output_dir)
        self._reporter = HTMLReporter(output_dir=self.config.project.report_output_dir)

    def set_project(self, project_name: str) -> None:
        """Set the current project context"""
        self._project_context = project_name

    def get_project(self) -> Optional[str]:
        """Get the current project context"""
        return self._project_context or self.config.project.default_project

    def generate_tests(
        self,
        user_story: str,
        application_url: Optional[str] = None,
        acceptance_criteria: Optional[List[str]] = None,
        project: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate test cases from user story and application URL.

        Args:
            user_story: User story description
            application_url: Application URL to test (required for automation)
            acceptance_criteria: List of acceptance criteria
            project: Project name (uses current project if None)
            **kwargs: Additional options (e.g., test_type, risk_level)

        Returns:
            Dictionary containing generated test cases (manual and automation)
        """
        # Set project context
        if project:
            self.set_project(project)

        project_name = self.get_project()
        acceptance_criteria = acceptance_criteria or []
        test_type = kwargs.get("test_type", "both")
        risk_level = kwargs.get("risk_level")

        # Get or create project
        with self._database.get_session() as session:
            db_project = session.query(Project).filter_by(name=project_name).first()
            if not db_project:
                db_project = Project(name=project_name, description=f"Project: {project_name}")
                session.add(db_project)
                session.flush()

            project_id = db_project.id

        # Request test generation from phoenix-intelligence
        intelligence_result = self._intelligence_client.generate_tests(
            user_story=user_story,
            application_url=application_url,
            acceptance_criteria=acceptance_criteria,
            test_type=test_type,
            risk_level=risk_level,
        )

        manual_tests_payload = intelligence_result.get("manual_tests", [])
        automation_tests_payload = intelligence_result.get("automation_tests", [])

        # Generate manual tests
        manual_tests = []
        if test_type in ["manual", "both"]:
            manual_test_data = self._manual_generator.generate(
                manual_tests=manual_tests_payload,
                user_story=user_story,
                application_url=application_url,
                risk_level=risk_level,
            )

            # Store manual tests in database
            with self._database.get_session() as session:
                for test_data in manual_test_data:
                    test_case = TestCase(
                        project_id=project_id,
                        name=test_data["name"],
                        description=test_data.get("description", user_story),
                        test_type=TestType.MANUAL,
                        risk_level=test_data.get("risk_level"),
                        steps=test_data.get("steps", []),
                        expected_result=test_data.get("expected_result"),
                        user_story=user_story,
                        acceptance_criteria=acceptance_criteria,
                        tags=test_data.get("tags", []),
                    )
                    session.add(test_case)
                    session.flush()
                    manual_tests.append({"id": test_case.id, **test_data})

        # Generate automation tests
        automation_tests = []
        if test_type in ["automation", "both"]:
            automation_test_data = self._automation_generator.generate(
                automation_tests=automation_tests_payload,
                user_story=user_story,
                application_url=application_url,
                acceptance_criteria=acceptance_criteria,
                test_category=kwargs.get("test_category", "ui"),
            )

            # Store automation tests in database
            with self._database.get_session() as session:
                for test_data in automation_test_data:
                    test_case = TestCase(
                        project_id=project_id,
                        name=test_data["name"],
                        description=test_data.get("description", user_story),
                        test_type=TestType.AUTOMATION,
                        risk_level=risk_level,
                        script_path=test_data.get("script_path"),
                        locators=test_data.get("locators", []),
                        user_story=user_story,
                        acceptance_criteria=acceptance_criteria,
                        tags=test_data.get("tags", []),
                    )
                    session.add(test_case)
                    session.flush()
                    automation_tests.append({"id": test_case.id, **test_data})

        return {
            "manual_tests": manual_tests,
            "automation_tests": automation_tests,
            "project": project_name,
            "metadata": {
                "user_story": user_story,
                "acceptance_criteria": acceptance_criteria,
                "test_type": test_type,
                "risk_level": risk_level,
            },
        }

    def execute_tests(
        self, test_ids: Optional[List[str]] = None, project: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Execute test cases.

        Args:
            test_ids: List of test IDs to execute (None = all tests in project)
            project: Project name (uses current project if None)
            **kwargs: Additional options (e.g., browser, parallel)

        Returns:
            Dictionary containing execution results
        """
        # Set project context
        if project:
            self.set_project(project)

        project_name = self.get_project()

        # Get project and test cases
        with self._database.get_session() as session:
            db_project = session.query(Project).filter_by(name=project_name).first()
            if not db_project:
                raise ValueError(f"Project '{project_name}' not found")

            query = session.query(TestCase).filter_by(
                project_id=db_project.id, test_type=TestType.AUTOMATION
            )
            if test_ids:
                query = query.filter(TestCase.id.in_([int(tid) for tid in test_ids]))

            test_cases = query.all()

            if not test_cases:
                return {
                    "status": ExecutionStatus.SKIPPED.value,
                    "message": "No automation tests found to execute",
                    "total_tests": 0,
                }

            # Create execution record
            execution = Execution(
                project_id=db_project.id,
                name=f"Execution {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                status=ExecutionStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                total_tests=len(test_cases),
            )
            session.add(execution)
            session.flush()
            execution_id = execution.id
            execution_started_at = execution.started_at
            script_paths = [tc.script_path for tc in test_cases if tc.script_path]

        # Execute tests
        execution_result = self._test_runner.run_tests(
            test_paths=script_paths, project_name=project_name, **kwargs
        )

        # Update execution record
        with self._database.get_session() as session:
            execution = session.query(Execution).filter_by(id=execution_id).first()
            if execution:
                execution.status = ExecutionStatus(
                    execution_result.get("status", ExecutionStatus.FAILED.value)
                )
                execution.completed_at = datetime.now(timezone.utc)
                execution.passed_tests = execution_result.get("passed_tests", 0)
                execution.failed_tests = execution_result.get("failed_tests", 0)
                execution.skipped_tests = execution_result.get("skipped_tests", 0)

                if execution.started_at:
                    started_at = execution.started_at
                    completed_at = execution.completed_at
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    if completed_at and completed_at.tzinfo is None:
                        completed_at = completed_at.replace(tzinfo=timezone.utc)
                    duration = (completed_at - started_at).total_seconds() if completed_at else 0
                    execution.duration_seconds = int(duration)
                execution_completed_at = execution.completed_at
                execution_duration_seconds = execution.duration_seconds
                execution_status = execution.status.value

        # Generate HTML report
        test_executions_data = []
        report_path = self._reporter.generate_report(
            execution_data={
                "id": execution_id,
                "project_name": project_name,
                "status": execution_status,
                "started_at": execution_started_at.isoformat() if execution_started_at else None,
                "completed_at": execution_completed_at.isoformat()
                if execution_completed_at
                else None,
                "duration_seconds": execution_duration_seconds,
                "total_tests": execution_result.get("total_tests", 0),
                "passed_tests": execution_result.get("passed_tests", 0),
                "failed_tests": execution_result.get("failed_tests", 0),
                "skipped_tests": execution_result.get("skipped_tests", 0),
            },
            test_executions=test_executions_data,
        )

        # Update execution with report path
        with self._database.get_session() as session:
            execution = session.query(Execution).filter_by(id=execution_id).first()
            if execution:
                execution.report_path = str(report_path)

        return {
            **execution_result,
            "execution_id": execution_id,
            "report_path": str(report_path),
        }

    def get_test_cases(
        self, project: Optional[str] = None, test_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get test cases for a project.

        Args:
            project: Project name (uses current project if None)
            test_type: Filter by type ('manual' or 'automation')

        Returns:
            List of test case dictionaries
        """
        if project:
            self.set_project(project)

        project_name = self.get_project()

        with self._database.get_session() as session:
            db_project = session.query(Project).filter_by(name=project_name).first()
            if not db_project:
                return []

            query = session.query(TestCase).filter_by(project_id=db_project.id)

            if test_type:
                test_type_enum = (
                    TestType.MANUAL if test_type.lower() == "manual" else TestType.AUTOMATION
                )
                query = query.filter_by(test_type=test_type_enum)

            test_cases = query.all()

            return [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "description": tc.description,
                    "test_type": tc.test_type.value,
                    "risk_level": tc.risk_level.value if tc.risk_level else None,
                    "steps": tc.steps,
                    "expected_result": tc.expected_result,
                    "script_path": tc.script_path,
                    "created_at": tc.created_at.isoformat() if tc.created_at else None,
                }
                for tc in test_cases
            ]

    def get_execution_results(
        self, execution_id: Optional[str] = None, project: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get execution results.

        Args:
            execution_id: Execution ID (None = latest execution)
            project: Project name (uses current project if None)

        Returns:
            Dictionary containing execution results and report path
        """
        if project:
            self.set_project(project)

        project_name = self.get_project()

        with self._database.get_session() as session:
            db_project = session.query(Project).filter_by(name=project_name).first()
            if not db_project:
                return {}

            if execution_id:
                execution = (
                    session.query(Execution)
                    .filter_by(id=int(execution_id), project_id=db_project.id)
                    .first()
                )
            else:
                execution = (
                    session.query(Execution)
                    .filter_by(project_id=db_project.id)
                    .order_by(Execution.created_at.desc())
                    .first()
                )

            if not execution:
                return {}

            # Get test executions
            test_executions = (
                session.query(TestExecution).filter_by(execution_id=execution.id).all()
            )

            return {
                "execution_id": execution.id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat()
                if execution.completed_at
                else None,
                "duration_seconds": execution.duration_seconds,
                "total_tests": execution.total_tests,
                "passed_tests": execution.passed_tests,
                "failed_tests": execution.failed_tests,
                "skipped_tests": execution.skipped_tests,
                "report_path": execution.report_path,
                "test_executions": [
                    {
                        "test_case_id": te.test_case_id,
                        "status": te.status.value,
                        "error_message": te.error_message,
                        "screenshot_path": te.screenshot_path,
                    }
                    for te in test_executions
                ],
            }
