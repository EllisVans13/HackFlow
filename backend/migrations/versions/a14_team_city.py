"""Persist team building style and exhibition consent."""
from alembic import op
import sqlalchemy as sa
revision='a14_team_city'
down_revision='a13_platform_owner'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('team',sa.Column('city_style',sa.String(20),nullable=False,server_default='workshop'))
    op.add_column('team',sa.Column('city_showcase',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.execute("UPDATE team SET city_style = CASE (id % 3) WHEN 0 THEN 'lab' WHEN 1 THEN 'workshop' ELSE 'tower' END")

def downgrade():
    with op.batch_alter_table('team') as batch:
        batch.drop_column('city_showcase')
        batch.drop_column('city_style')
