import re

from fastapi import APIRouter, HTTPException

from app.visas.fees import fees
from app.visas.rules import rule_for, view

router = APIRouter(prefix="/api/visa", tags=["Visas"])
WAIT_S = 25.0  # a first lookup searches the web and reads the results: the chip waits with a spinner


@router.get("/{pair}")
async def visa(pair: str) -> dict:
    """The rule and the fee for «KZ-US» (passport, destination): the card's chip asks when the fee was not
    ready while the cards were drawn. The fee is cached, so only the first one waits."""
    if not re.fullmatch(r"[A-Za-z]{2}-[A-Za-z]{2}", pair):
        raise HTTPException(status_code=422, detail="pair is two ISO country codes: KZ-US")
    passport, destination = pair.upper().split("-")
    rule = rule_for(destination, passport)
    if rule is None:
        raise HTTPException(status_code=404, detail="no visa rule for this pair")
    fee = await fees().get(rule, WAIT_S)
    return {**view(rule), "fee": fee.view() if fee else None}
