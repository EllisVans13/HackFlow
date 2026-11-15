"""Dedicated mentor profiles, team selection, and repeatable Russian learning pack."""
from alembic import op
import sqlalchemy as sa

revision='a17_mentors_learning'
down_revision='a16_merge_legacy_histories'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('user',sa.Column('mentor_bio',sa.Text(),nullable=True))
    op.add_column('user',sa.Column('mentor_skills',sa.String(300),nullable=True))
    with op.batch_alter_table('team') as batch:
        batch.add_column(sa.Column('mentor_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_team_mentor','user',['mentor_id'],['id'])
        batch.create_index('ix_team_mentor_id',['mentor_id'])
    with op.batch_alter_table('material') as batch:
        batch.add_column(sa.Column('catalog_key',sa.String(80),nullable=True))
        # Do not label historical organizer materials as Russian without checking them.
        batch.add_column(sa.Column('language',sa.String(10),nullable=False,server_default='unknown'))
        batch.create_unique_constraint('uq_material_catalog_key',['hackathon_id','catalog_key'])
    from hackflow.learning_seed_v1 import populate_learning
    populate_learning(op.get_bind())


def downgrade():
    # Added learning rows are educational data; don't silently delete them on rollback.
    with op.batch_alter_table('material') as batch:
        batch.drop_constraint('uq_material_catalog_key',type_='unique')
        batch.drop_column('catalog_key')
        batch.drop_column('language')
    with op.batch_alter_table('team') as batch:
        batch.drop_index('ix_team_mentor_id')
        batch.drop_constraint('fk_team_mentor',type_='foreignkey')
        batch.drop_column('mentor_id')
    op.drop_column('user','mentor_skills')
    op.drop_column('user','mentor_bio')
