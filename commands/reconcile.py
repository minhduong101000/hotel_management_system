import json

import click

from extensions import db
from models import Hotel
from services import reconciliation_service


def register_reconciliation_commands(app):
    @app.cli.command("reconcile-business-data")
    @click.option(
        "--hotel-slug",
        required=True,
        help="Target hotel slug.",
    )
    @click.option(
        "--apply",
        is_flag=True,
        help="Apply only evidence-backed repairs.",
    )
    @click.option(
        "--confirm-apply",
        is_flag=True,
        help="Confirm that the dry-run report was approved.",
    )
    @click.option(
        "--backup-acknowledged",
        is_flag=True,
        help="Confirm that a restorable backup exists.",
    )
    def reconcile_business_data(
        hotel_slug,
        apply,
        confirm_apply,
        backup_acknowledged,
    ):
        """Reconcile business invariants for one hotel."""
        if apply and not confirm_apply:
            raise click.ClickException(
                "Apply requires --confirm-apply after dry-run approval."
            )
        if apply and not backup_acknowledged:
            raise click.ClickException(
                "Apply requires --backup-acknowledged."
            )

        hotel = Hotel.query.filter_by(slug=hotel_slug).first()
        if hotel is None:
            raise click.ClickException(
                f"Hotel slug {ascii(hotel_slug)} was not found."
            )
        hotel_id = hotel.id
        tenant_slug = hotel.slug
        db.session.rollback()

        if apply:
            try:
                report = reconciliation_service.run_reconciliation(
                    hotel_id=hotel_id,
                    apply=True,
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise click.ClickException(
                    "Reconciliation failed; tenant rollback completed."
                )
        else:
            try:
                report = reconciliation_service.run_reconciliation(
                    hotel_id=hotel_id,
                    apply=False,
                )
            finally:
                db.session.rollback()

        report = {
            "mode": "apply" if apply else "dry-run",
            "tenant": tenant_slug,
            **report,
        }
        click.echo(
            json.dumps(
                report,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
