"""Difficulty and administrator moderation; preserve existing events."""
from alembic import op
import sqlalchemy as sa
revision='a12_hackathon_review'
down_revision='a11_team_invitations'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('hackathon',sa.Column('difficulty',sa.String(20),nullable=False,server_default='easy'))
    op.add_column('hackathon',sa.Column('approval',sa.String(20),nullable=False,server_default='approved'))
    op.add_column('hackathon',sa.Column('review_comment',sa.Text(),nullable=True))
def downgrade():
    op.drop_column('hackathon','review_comment')
    op.drop_column('hackathon','approval')
    op.drop_column('hackathon','difficulty')
