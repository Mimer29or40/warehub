from __future__ import annotations


class WarehubException(Exception):
    """Base Exception"""


class DatabaseException(WarehubException):
    """Base Database Exception"""
