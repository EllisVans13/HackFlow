"""Separate team deadline and idempotent demo identifiers."""
from alembic import op
import sqlalchemy as sa
revision='a10_self_registration'
down_revision='55e9b1bb7a5d'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('hackathon',sa.Column('team_deadline',sa.DateTime(),nullable=True))
    op.add_column('hackathon',sa.Column('demo_key',sa.String(80),nullable=True))
    op.create_unique_constraint('uq_hackathon_demo_key','hackathon',['demo_key'])
    op.execute('UPDATE hackathon SET team_deadline = registration_deadline')
def downgrade():
    op.drop_constraint('uq_hackathon_demo_key','hackathon',type_='unique')
    op.drop_column('hackathon','demo_key')
    op.drop_column('hackathon','team_deadline')
