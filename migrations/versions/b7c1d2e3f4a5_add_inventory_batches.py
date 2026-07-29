"""Add inventory batches and immutable inventory movements.

Revision ID: b7c1d2e3f4a5
Revises: f5a9b3c7d0e2
"""
from datetime import date

from alembic import op
import sqlalchemy as sa


revision = 'b7c1d2e3f4a5'
down_revision = 'f5a9b3c7d0e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'inventory_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hotel_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('expense_id', sa.Integer(), nullable=True),
        sa.Column('batch_code', sa.String(length=64), nullable=False),
        sa.Column('received_at', sa.Date(), nullable=False),
        sa.Column('expires_at', sa.Date(), nullable=True),
        sa.Column('quantity_received', sa.Integer(), nullable=False),
        sa.Column('quantity_available', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id']),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hotel_id', 'batch_code', name='_hotel_inventory_batch_code_uc'),
    )
    op.create_index('ix_inventory_batches_hotel_id', 'inventory_batches', ['hotel_id'])
    op.create_index('ix_inventory_batches_inventory_item_id', 'inventory_batches', ['inventory_item_id'])

    op.create_table(
        'inventory_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hotel_id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('expense_id', sa.Integer(), nullable=True),
        sa.Column('booking_service_id', sa.Integer(), nullable=True),
        sa.Column('movement_type', sa.String(length=20), nullable=False),
        sa.Column('quantity_delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['batch_id'], ['inventory_batches.id']),
        sa.ForeignKeyConstraint(['booking_service_id'], ['booking_services.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id']),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id']),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inventory_movements_hotel_id', 'inventory_movements', ['hotel_id'])
    op.create_index('ix_inventory_movements_inventory_item_id', 'inventory_movements', ['inventory_item_id'])
    op.create_index('ix_inventory_movements_batch_id', 'inventory_movements', ['batch_id'])

    op.create_table(
        'booking_service_batch_allocations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hotel_id', sa.Integer(), nullable=False),
        sa.Column('booking_service_id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['batch_id'], ['inventory_batches.id']),
        sa.ForeignKeyConstraint(['booking_service_id'], ['booking_services.id']),
        sa.ForeignKeyConstraint(['hotel_id'], ['hotels.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_service_batch_allocations_hotel_id', 'booking_service_batch_allocations', ['hotel_id'])
    op.create_index('ix_booking_service_batch_allocations_booking_service_id', 'booking_service_batch_allocations', ['booking_service_id'])
    op.create_index('ix_booking_service_batch_allocations_batch_id', 'booking_service_batch_allocations', ['batch_id'])

    bind = op.get_bind()
    legacy_items = bind.execute(sa.text(
        'SELECT id, hotel_id, code, quantity, price FROM inventory_items WHERE quantity > 0'
    )).mappings().all()
    batch_table = sa.table(
        'inventory_batches',
        sa.column('hotel_id', sa.Integer), sa.column('inventory_item_id', sa.Integer),
        sa.column('batch_code', sa.String), sa.column('received_at', sa.Date),
        sa.column('quantity_received', sa.Integer), sa.column('quantity_available', sa.Integer),
        sa.column('unit_cost', sa.Numeric), sa.column('status', sa.String),
    )
    movement_table = sa.table(
        'inventory_movements',
        sa.column('hotel_id', sa.Integer), sa.column('inventory_item_id', sa.Integer),
        sa.column('batch_id', sa.Integer), sa.column('movement_type', sa.String),
        sa.column('quantity_delta', sa.Integer), sa.column('reason', sa.String),
    )
    for item in legacy_items:
        result = bind.execute(batch_table.insert().values(
            hotel_id=item['hotel_id'],
            inventory_item_id=item['id'],
            batch_code=f"TONDAU-{item['code']}-{item['id']}",
            received_at=date.today(),
            quantity_received=item['quantity'],
            quantity_available=item['quantity'],
            unit_cost=item['price'] or 0,
            status='active',
        ))
        batch_id = result.inserted_primary_key[0] if result.inserted_primary_key else result.lastrowid
        bind.execute(movement_table.insert().values(
            hotel_id=item['hotel_id'],
            inventory_item_id=item['id'],
            batch_id=batch_id,
            movement_type='receipt',
            quantity_delta=item['quantity'],
            reason='Tồn đầu',
        ))


def downgrade():
    op.drop_index('ix_booking_service_batch_allocations_batch_id', table_name='booking_service_batch_allocations')
    op.drop_index('ix_booking_service_batch_allocations_booking_service_id', table_name='booking_service_batch_allocations')
    op.drop_index('ix_booking_service_batch_allocations_hotel_id', table_name='booking_service_batch_allocations')
    op.drop_table('booking_service_batch_allocations')
    op.drop_index('ix_inventory_movements_batch_id', table_name='inventory_movements')
    op.drop_index('ix_inventory_movements_inventory_item_id', table_name='inventory_movements')
    op.drop_index('ix_inventory_movements_hotel_id', table_name='inventory_movements')
    op.drop_table('inventory_movements')
    op.drop_index('ix_inventory_batches_inventory_item_id', table_name='inventory_batches')
    op.drop_index('ix_inventory_batches_hotel_id', table_name='inventory_batches')
    op.drop_table('inventory_batches')
