"""Mock data package for Arbiter AI.

Provides rich, realistic fake data for every entity in the system.
Used when APP_MODE=mock to serve API responses without hitting
any real database or external service.

Contents:
    fixtures.py  — Static fixture data (users, sessions, rulings, etc.)
    factory.py   — Factory functions for generating mock objects on demand

Called by: mock_routes.py, mock providers
Depends on: Nothing (zero external dependencies by design)
"""
