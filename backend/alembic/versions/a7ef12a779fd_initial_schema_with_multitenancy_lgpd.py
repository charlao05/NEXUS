"""initial_schema_with_multitenancy_lgpd

Revision ID: a7ef12a779fd
Revises: 
Create Date: 2026-02-12 22:31:22.191200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7ef12a779fd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Appointments — add FK to users (user_id column já existe pela migration anterior)
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_appointments_user_id', 'users', ['user_id'], ['id'])

    # Clients — add user_id column + indexes + FK
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_clients_user', ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_clients_user_id', 'users', ['user_id'], ['id'])

    # Invoices — add user_id
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_invoices_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_invoices_user_id', 'users', ['user_id'], ['id'])

    # Transactions — add user_id
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_transactions_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_transactions_user_id', 'users', ['user_id'], ['id'])

    # Users — add LGPD + email verification + password reset fields
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('password_reset_token', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('password_reset_expires', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('lgpd_consent', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('lgpd_consent_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('lgpd_consent_ip', sa.String(length=45), nullable=True))

    # WebTasks — add user_id
    with op.batch_alter_table('web_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_web_tasks_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_web_tasks_user_id', 'users', ['user_id'], ['id'])

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('web_tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_web_tasks_user_id', type_='foreignkey')
        batch_op.drop_index('ix_web_tasks_user_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('lgpd_consent_ip')
        batch_op.drop_column('lgpd_consent_at')
        batch_op.drop_column('lgpd_consent')
        batch_op.drop_column('password_reset_expires')
        batch_op.drop_column('password_reset_token')
        batch_op.drop_column('email_verified')

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_transactions_user_id', type_='foreignkey')
        batch_op.drop_index('ix_transactions_user_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_constraint('fk_invoices_user_id', type_='foreignkey')
        batch_op.drop_index('ix_invoices_user_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_clients_user_id', type_='foreignkey')
        batch_op.drop_index('ix_clients_user')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_appointments_user_id', type_='foreignkey')

    # ### end Alembic commands ###
