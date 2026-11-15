"""Issue personal podium certificates and backfill published completed events."""
from datetime import datetime, timezone
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision='a15_award_certificates'
down_revision='a14_team_city'
branch_labels=None
depends_on=None

def upgrade():
    table=op.create_table('award_certificate',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('public_id',sa.String(32),nullable=False,unique=True),
        sa.Column('hackathon_id',sa.Integer(),sa.ForeignKey('hackathon.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('user.id',ondelete='CASCADE'),nullable=False),
        sa.Column('result_id',sa.Integer(),sa.ForeignKey('personal_result.id',ondelete='CASCADE'),nullable=False),
        sa.Column('recipient_name',sa.String(64),nullable=False),
        sa.Column('team_name',sa.String(100),nullable=False),
        sa.Column('event_title',sa.String(200),nullable=False),
        sa.Column('organizer_name',sa.String(64),nullable=False),
        sa.Column('place',sa.Integer(),nullable=False),
        sa.Column('is_demo',sa.Boolean(),nullable=False),
        sa.Column('issued_at',sa.DateTime(),nullable=False),
        sa.Column('revoked_at',sa.DateTime()),
        sa.CheckConstraint('place BETWEEN 1 AND 3',name='certificate_podium_place'))
    op.create_index('ix_award_certificate_hackathon_id','award_certificate',['hackathon_id'])
    op.create_index('ix_award_certificate_user_id','award_certificate',['user_id'])
    op.create_index('uq_current_certificate','award_certificate',['hackathon_id','user_id'],unique=True,
                    postgresql_where=sa.text('revoked_at IS NULL'),sqlite_where=sa.text('revoked_at IS NULL'))
    rows=op.get_bind().execute(sa.text('''SELECT r.id AS result_id,r.user_id,r.hackathon_id,r.team_name,r.place,
        u.nickname AS recipient_name,h.title AS event_title,h.demo_key,
        (SELECT organizer.nickname FROM event_role er JOIN "user" organizer ON organizer.id=er.user_id
         WHERE er.hackathon_id=h.id AND er.role='organizer' ORDER BY er.id LIMIT 1) AS organizer_name
        FROM personal_result r JOIN "user" u ON u.id=r.user_id JOIN hackathon h ON h.id=r.hackathon_id
        WHERE r.place BETWEEN 1 AND 3 AND h.results_published=true AND h.status='completed' ''')).mappings().all()
    issued=datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        values=dict(row);values['is_demo']=bool(values.pop('demo_key'))
        values['organizer_name']=values['organizer_name'] or 'Организаторы хакатона'
        op.get_bind().execute(table.insert().values(**values,public_id=uuid4().hex,issued_at=issued))

def downgrade():
    op.drop_table('award_certificate')
