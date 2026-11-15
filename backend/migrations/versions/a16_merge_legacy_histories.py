"""Allow databases from main, adele and the original feature branch to upgrade."""

revision = 'a16_merge_legacy_histories'
down_revision = ('a15_award_certificates', 'adele_compat_heads')
branch_labels = None
depends_on = None


def upgrade():
    # Ancestor migrations create missing tables and preserve existing award data.
    # Keep the legacy award table: existing certificates must not be discarded.
    pass


def downgrade():
    raise RuntimeError(
        'Merged migration histories share award data. Restore a backup to roll back.'
    )
