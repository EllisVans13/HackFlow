"""Separate team deadline and idempotent demo identifiers."""
from alembic import op
import sqlalchemy as sa
revision='a10_self_registration'
down_revision='55e9b1bb7a5d'
branch_labels=None
depends_on=None
def upgrade():
    # SQLite table recreation otherwise loses the original unnamed CHECK.
    constraints=[sa.CheckConstraint('team_size > 0 AND team_size <= 20',name='ck_hackathon_team_size')] if op.get_bind().dialect.name=='sqlite' else []
    with op.batch_alter_table('hackathon',table_args=constraints) as batch:
        batch.add_column(sa.Column('team_deadline',sa.DateTime(),nullable=True))
        batch.add_column(sa.Column('demo_key',sa.String(80),nullable=True))
        batch.create_unique_constraint('uq_hackathon_demo_key',['demo_key'])
    op.execute('UPDATE hackathon SET team_deadline = registration_deadline')
def downgrade():
    with op.batch_alter_table('hackathon') as batch:
        batch.drop_constraint('uq_hackathon_demo_key',type_='unique')
        batch.drop_column('demo_key')
        batch.drop_column('team_deadline')
