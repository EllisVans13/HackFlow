"""Recognize both known histories while preserving application behaviour in adele."""
revision='adele_compat_heads'
down_revision=('adele_awards','a15_merge_city_awards')
branch_labels=None
depends_on=None

def upgrade():
    pass

def downgrade():
    raise RuntimeError('The merged histories share award data. Restore a backup for rollback instead of dropping shared tables.')
