"""Platform owner separate from administrator role."""
from alembic import op
import sqlalchemy as sa
revision='a13_platform_owner'
down_revision='a12_hackathon_review'
branch_labels=None
depends_on=None
def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('is_owner',sa.Boolean(),nullable=False,server_default=sa.false()))
        batch.create_check_constraint('owner_is_active_admin',"NOT is_owner OR (role='admin' AND NOT blocked)")
    op.execute("UPDATE \"user\" SET is_owner = true, blocked = false WHERE email = 'admin@hackflow.test' AND role = 'admin'")
    op.create_index('uq_platform_owner','user',['is_owner'],unique=True,postgresql_where=sa.text('is_owner'),sqlite_where=sa.text('is_owner'))
def downgrade():
    op.drop_index('uq_platform_owner',table_name='user')
    with op.batch_alter_table('user') as batch:
        batch.drop_constraint('owner_is_active_admin',type_='check')
        batch.drop_column('is_owner')
