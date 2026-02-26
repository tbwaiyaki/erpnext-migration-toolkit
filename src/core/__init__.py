"""
Core types for financial primitives.

Exports:
    Money: Monetary amount with currency
    get_currency_precision: Currency decimal precision lookup
"""

from .money import Money, get_currency_precision

__all__ = ['Money', 'get_currency_precision']
