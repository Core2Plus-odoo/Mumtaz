"""Pure-Python jewellery pricing engine.

No Odoo imports, so it can be unit-tested anywhere. Every price shown by the
product must come from ``price_piece`` using a gold rate read from the
database (``jewellery.gold.rate.get_current``); never from a model or a
hard-coded figure.

All arithmetic uses ``Decimal``. Each component is rounded to ``places``
before summing, so a breakdown always adds up to its total.
"""
from decimal import ROUND_HALF_UP, Decimal

GRAMS_PER_TOLA = Decimal("11.6638038")
GRAMS_PER_TROY_OUNCE = Decimal("31.1034768")
UNIT_GRAMS = {
    "gram": Decimal(1),
    "tola": GRAMS_PER_TOLA,
    "ounce": GRAMS_PER_TROY_OUNCE,
}
MAKING_TYPES = ("percent", "per_gram", "fixed")


def _d(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _round(value, places=2):
    return _d(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def to_grams(value, unit="gram"):
    """Convert a weight in ``unit`` (gram, tola, ounce) to grams."""
    if unit not in UNIT_GRAMS:
        raise ValueError("Unknown weight unit: %s" % unit)
    return _d(value) * UNIT_GRAMS[unit]


def rate_per_unit(rate_per_gram, unit="gram", places=2):
    """Rate for one ``unit`` of metal, given the rate per gram."""
    if unit not in UNIT_GRAMS:
        raise ValueError("Unknown weight unit: %s" % unit)
    return _round(_d(rate_per_gram) * UNIT_GRAMS[unit], places)


def purity(karat=None, fineness=None):
    """Fraction of pure gold. ``fineness`` (parts per thousand, for example
    916 for 22K) takes precedence over ``karat`` (karat / 24)."""
    if fineness is not None:
        fine = _d(fineness)
        if not 0 < fine <= 1000:
            raise ValueError("Fineness must be between 0 and 1000.")
        return fine / Decimal(1000)
    if karat is None:
        raise ValueError("Karat or fineness is required.")
    k = _d(karat)
    if not 0 < k <= 24:
        raise ValueError("Karat must be between 0 and 24.")
    return k / Decimal(24)


def price_piece(
    *,
    net_weight_g,
    karat=None,
    fineness=None,
    rate_24k_per_g,
    wastage_pct=0,
    making_type="percent",
    making_value=0,
    making_discount_pct=0,
    stones_value=0,
    vat_rate=0,
    places=2,
):
    """Price one piece. Returns a dict of Decimals.

    ``making_type``: ``percent`` of the metal value, ``per_gram`` of net
    weight, or a ``fixed`` amount. ``making_discount_pct`` is a trade discount
    on the making charge only (dealer tiers); the metal is never discounted.
    ``vat_rate`` is a percentage, for example 5 for 5%.
    """
    if making_type not in MAKING_TYPES:
        raise ValueError("Unknown making type: %s" % making_type)
    weight = _d(net_weight_g)
    rate = _d(rate_24k_per_g)
    wastage = _d(wastage_pct)
    value = _d(making_value)
    discount = _d(making_discount_pct)
    stones = _d(stones_value)
    vat = _d(vat_rate)
    for name, number in (
        ("net weight", weight), ("rate", rate), ("wastage", wastage),
        ("making value", value), ("stones value", stones), ("VAT rate", vat),
    ):
        if number < 0:
            raise ValueError("%s cannot be negative." % name.capitalize())
    if not 0 <= discount <= 100:
        raise ValueError("Making discount must be between 0 and 100.")

    fine_weight = weight * purity(karat, fineness)
    metal_exact = fine_weight * rate
    metal_value = _round(metal_exact, places)
    wastage_value = _round(metal_exact * wastage / Decimal(100), places)
    if making_type == "percent":
        making_exact = metal_exact * value / Decimal(100)
    elif making_type == "per_gram":
        making_exact = weight * value
    else:
        making_exact = value
    making_charge = _round(
        making_exact * (Decimal(100) - discount) / Decimal(100), places)
    stones_value = _round(stones, places)
    subtotal = metal_value + wastage_value + making_charge + stones_value
    vat_amount = _round(subtotal * vat / Decimal(100), places)
    return {
        "fine_weight_g": fine_weight.quantize(Decimal("0.0001")),
        "rate_24k_per_g": rate,
        "metal_value": metal_value,
        "wastage_value": wastage_value,
        "making_charge": making_charge,
        "stones_value": stones_value,
        "subtotal": subtotal,
        "vat": vat_amount,
        "total": subtotal + vat_amount,
    }


def old_gold_value(
    *, gross_weight_g, karat=None, fineness=None, melt_loss_pct=0,
    rate_24k_per_g, buyback_discount_pct=0, places=2,
):
    """Value of scrap gold taken in exchange.

    Fine weight is gross weight x purity, reduced by melt loss. The buy-back
    discount is the shop's margin on the 24K rate. Returns a dict of Decimals.
    """
    gross = _d(gross_weight_g)
    loss = _d(melt_loss_pct)
    discount = _d(buyback_discount_pct)
    if gross < 0 or _d(rate_24k_per_g) < 0:
        raise ValueError("Weight and rate cannot be negative.")
    if not 0 <= loss < 100 or not 0 <= discount < 100:
        raise ValueError("Melt loss and discount must be between 0 and 100.")
    fine_before = gross * purity(karat, fineness)
    fine_after = fine_before * (Decimal(100) - loss) / Decimal(100)
    applied_rate = _d(rate_24k_per_g) * (Decimal(100) - discount) / Decimal(100)
    return {
        "fine_weight_g": fine_after.quantize(Decimal("0.0001")),
        "melt_loss_g": (fine_before - fine_after).quantize(Decimal("0.0001")),
        "applied_rate_per_g": _round(applied_rate, 4),
        "value": _round(fine_after * applied_rate, places),
    }
