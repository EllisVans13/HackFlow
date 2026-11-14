"""Persist captain invitations and recipient decisions."""
from alembic import op
import sqlalchemy as sa
revision='a11_team_invitations'
down_revision='a10_self_registration'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('team_invitation',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('team_id',sa.Integer(),sa.ForeignKey('team.id',ondelete='CASCADE'),nullable=False),sa.Column('user_id',sa.Integer(),sa.ForeignKey('user.id'),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('team_id','user_id',name='uq_team_invitation_recipient'))
    op.create_index('ix_team_invitation_team_id','team_invitation',['team_id'])
    op.create_index('ix_team_invitation_user_id','team_invitation',['user_id'])
def downgrade():
    op.drop_table('team_invitation')
