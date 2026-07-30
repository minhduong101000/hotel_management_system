from commands.development import register_development_commands
from commands.reconcile import register_reconciliation_commands


def register_commands(app):
    register_development_commands(app)
    register_reconciliation_commands(app)
