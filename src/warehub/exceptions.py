from __future__ import annotations


class WarehubException(Exception):
    """Base Exception"""


class DatabaseException(WarehubException):
    """Base Database Exception"""


class InvalidDistribution(WarehubException):
    """Raised when a distribution is invalid."""
