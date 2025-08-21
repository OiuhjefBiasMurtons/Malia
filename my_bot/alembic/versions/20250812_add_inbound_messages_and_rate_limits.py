# alembic revision: add inbound_messages and rate_limits
from alembic import op
import sqlalchemy as sa

# Reemplaza por el ID real si generas con 'alembic revision'
revision = '20250812_add_inbound_and_limits'
down_revision = 'afba68badda8'  # o pon aquí tu baseline si hiciste baseline
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'inbound_messages',
        sa.Column('message_sid', sa.Text(), primary_key=True),
        sa.Column('from_number', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('received_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False)
    )

    op.create_table(
        'rate_limits',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('from_number', sa.Text(), nullable=False),
        sa.Column('window_start', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint(
        'rate_limits_unique', 'rate_limits', ['from_number', 'window_start']
    )
    op.create_index(
        'idx_rate_limits_number_window',
        'rate_limits',
        ['from_number', 'window_start']
    )

def downgrade():
    op.drop_index('idx_rate_limits_number_window', table_name='rate_limits')
    op.drop_constraint('rate_limits_unique', 'rate_limits', type_='unique')
    op.drop_table('rate_limits')
    op.drop_table('inbound_messages')
