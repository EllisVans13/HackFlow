"""Weighted peer assessment, anonymous project files and scheduled meetings."""
from alembic import op
import sqlalchemy as sa
revision='a18_peer_meetings'
down_revision='a17_mentors_learning'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('user',sa.Column('is_demo',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('hackathon',sa.Column('peer_enabled',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.execute("UPDATE hackathon SET peer_enabled=true WHERE results_published=false AND peer_published=false AND status!='completed' AND NOT EXISTS (SELECT 1 FROM peer_assignment pa JOIN submission s ON s.id=pa.submission_id JOIN team t ON t.id=s.team_id WHERE t.hackathon_id=hackathon.id)")
    op.add_column('schedule',sa.Column('duration_minutes',sa.Integer(),nullable=False,server_default='60'))
    op.add_column('schedule',sa.Column('provider',sa.String(20),nullable=False,server_default='link'))
    with op.batch_alter_table('submission') as batch:
        batch.add_column(sa.Column('anonymous_file_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_submission_anonymous_file','upload',['anonymous_file_id'],['id'])

def downgrade():
    with op.batch_alter_table('submission') as batch:
        batch.drop_constraint('fk_submission_anonymous_file',type_='foreignkey')
        batch.drop_column('anonymous_file_id')
    op.drop_column('schedule','provider');op.drop_column('schedule','duration_minutes')
    op.drop_column('hackathon','peer_enabled');op.drop_column('user','is_demo')
