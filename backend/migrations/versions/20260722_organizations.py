"""Add organizations and memberships."""
from alembic import op
import sqlalchemy as sa
revision = "20260722_organizations"
down_revision = "20260722_prompt_revisions"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("organizations", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("owner_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False))
    op.create_table("organization_members", sa.Column("id", sa.Integer, primary_key=True), sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False), sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False), sa.Column("role", sa.String(20), nullable=False), sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_member"))
    op.add_column("projects", sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=True))
    op.execute('INSERT INTO organizations (name, owner_id) SELECT CONCAT(\'Personal organization \', id), id FROM "user"')
    op.execute('INSERT INTO organization_members (organization_id, user_id, role) SELECT o.id, o.owner_id, \'owner\' FROM organizations o')
    op.execute('UPDATE projects p SET organization_id = o.id FROM organizations o WHERE o.owner_id = p.user_id')
    op.alter_column("projects", "organization_id", nullable=False)
def downgrade(): op.drop_column("projects", "organization_id"); op.drop_table("organization_members"); op.drop_table("organizations")
