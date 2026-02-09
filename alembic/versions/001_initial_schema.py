"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=True)

    # Create test_cases table
    op.create_table(
        'test_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('test_type', sa.Enum('MANUAL', 'AUTOMATION', name='testtype'), nullable=False),
        sa.Column('risk_level', sa.Enum('SMOKE', 'REGRESSION', 'EDGE', name='testrisk'), nullable=True),
        sa.Column('steps', sa.JSON(), nullable=True),
        sa.Column('expected_result', sa.Text(), nullable=True),
        sa.Column('script_path', sa.String(length=500), nullable=True),
        sa.Column('locators', sa.JSON(), nullable=True),
        sa.Column('user_story', sa.Text(), nullable=True),
        sa.Column('acceptance_criteria', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_cases_id'), 'test_cases', ['id'], unique=False)
    op.create_index(op.f('ix_test_cases_project_id'), 'test_cases', ['project_id'], unique=False)
    op.create_index(op.f('ix_test_cases_test_type'), 'test_cases', ['test_type'], unique=False)
    op.create_index(op.f('ix_test_cases_risk_level'), 'test_cases', ['risk_level'], unique=False)

    # Create executions table
    op.create_table(
        'executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'ERROR', name='executionstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('total_tests', sa.Integer(), nullable=False),
        sa.Column('passed_tests', sa.Integer(), nullable=False),
        sa.Column('failed_tests', sa.Integer(), nullable=False),
        sa.Column('skipped_tests', sa.Integer(), nullable=False),
        sa.Column('report_path', sa.String(length=500), nullable=True),
        sa.Column('execution_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_executions_id'), 'executions', ['id'], unique=False)
    op.create_index(op.f('ix_executions_project_id'), 'executions', ['project_id'], unique=False)
    op.create_index(op.f('ix_executions_status'), 'executions', ['status'], unique=False)

    # Create test_executions table
    op.create_table(
        'test_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('test_case_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'ERROR', name='executionstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('screenshot_path', sa.String(length=500), nullable=True),
        sa.Column('logs', sa.JSON(), nullable=True),
        sa.Column('test_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
        sa.ForeignKeyConstraint(['test_case_id'], ['test_cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_executions_id'), 'test_executions', ['id'], unique=False)
    op.create_index(op.f('ix_test_executions_execution_id'), 'test_executions', ['execution_id'], unique=False)
    op.create_index(op.f('ix_test_executions_test_case_id'), 'test_executions', ['test_case_id'], unique=False)
    op.create_index(op.f('ix_test_executions_status'), 'test_executions', ['status'], unique=False)

    # Create locators table
    op.create_table(
        'locators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('element_name', sa.String(length=255), nullable=False),
        sa.Column('locator_strategy', sa.String(length=50), nullable=False),
        sa.Column('locator_value', sa.String(length=500), nullable=False),
        sa.Column('locator_string', sa.String(length=500), nullable=False),
        sa.Column('is_stable', sa.Boolean(), nullable=False),
        sa.Column('last_validated_at', sa.DateTime(), nullable=True),
        sa.Column('validation_count', sa.Integer(), nullable=False),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('page_url', sa.String(length=1000), nullable=True),
        sa.Column('page_title', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_locators_id'), 'locators', ['id'], unique=False)
    op.create_index(op.f('ix_locators_project_id'), 'locators', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_locators_project_id'), table_name='locators')
    op.drop_index(op.f('ix_locators_id'), table_name='locators')
    op.drop_table('locators')
    op.drop_index(op.f('ix_test_executions_status'), table_name='test_executions')
    op.drop_index(op.f('ix_test_executions_test_case_id'), table_name='test_executions')
    op.drop_index(op.f('ix_test_executions_execution_id'), table_name='test_executions')
    op.drop_index(op.f('ix_test_executions_id'), table_name='test_executions')
    op.drop_table('test_executions')
    op.drop_index(op.f('ix_executions_status'), table_name='executions')
    op.drop_index(op.f('ix_executions_project_id'), table_name='executions')
    op.drop_index(op.f('ix_executions_id'), table_name='executions')
    op.drop_table('executions')
    op.drop_index(op.f('ix_test_cases_risk_level'), table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_test_type'), table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_project_id'), table_name='test_cases')
    op.drop_index(op.f('ix_test_cases_id'), table_name='test_cases')
    op.drop_table('test_cases')
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_index(op.f('ix_projects_id'), table_name='projects')
    op.drop_table('projects')
