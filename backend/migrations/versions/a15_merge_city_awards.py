"""Merge existing city and awards databases without rewriting applied revisions."""
revision='a15_merge_city_awards'
down_revision=('a14_team_city','a14_awards')
branch_labels=None
depends_on=None

def upgrade():
    pass

def downgrade():
    pass
