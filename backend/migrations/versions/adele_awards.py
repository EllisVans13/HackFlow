"""Participation certificates and prize diplomas."""
from alembic import op
import sqlalchemy as sa
revision='adele_awards'
down_revision='55e9b1bb7a5d'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('award',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('user.id'),nullable=False),sa.Column('hackathon_id',sa.Integer(),sa.ForeignKey('hackathon.id'),nullable=False),sa.Column('kind',sa.String(20),nullable=False),sa.Column('token',sa.String(64),unique=True,nullable=False),sa.Column('recipient',sa.String(64),nullable=False),sa.Column('event_title',sa.String(200),nullable=False),sa.Column('organizers',sa.Text(),nullable=False),sa.Column('place',sa.Integer()),sa.Column('issued_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('user_id','hackathon_id','kind',name='uq_award_user_event_kind'))
    op.create_index('ix_award_user_id','award',['user_id'])
def downgrade():op.drop_table('award')
