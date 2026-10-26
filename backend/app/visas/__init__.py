"""Visas for the traveller's own passport: the rule for every country (Passport Index) and what it costs
(found on the web once, then cached). See rules.py and fees.py."""

from app.visas.fees import NoFees, VisaFee, VisaFees, configure, fees
from app.visas.rules import VisaRule, current_passport, label, passport_of, rule_for, sentence, view

__all__ = [
    "NoFees",
    "VisaFee",
    "VisaFees",
    "VisaRule",
    "configure",
    "current_passport",
    "fees",
    "label",
    "passport_of",
    "rule_for",
    "sentence",
    "view",
]
