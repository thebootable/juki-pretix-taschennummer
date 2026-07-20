from django.core.exceptions import ValidationError
from django.db import transaction

from .models import BagNumber, ItemNumberConfig, NumberRange


def assign_number(position):
    """
    Assigns the smallest free number >= range.start for an OrderPosition.
    Returns None if the product has no number range or the position already
    has a number. SELECT FOR UPDATE protects against race conditions.
    """
    try:
        config = position.item.bagnumber_config
    except ItemNumberConfig.DoesNotExist:
        return None

    if BagNumber.objects.filter(position=position).exists():
        return position.bagnumber

    event = position.order.event

    with transaction.atomic():
        rng = NumberRange.objects.select_for_update().get(
            pk=config.number_range_id
        )
        used = set(
            BagNumber.objects
            .filter(event=event, number__gte=rng.start)
            .values_list("number", flat=True)
        )
        n = rng.start
        while n in used:
            n += 1
        if rng.end is not None and n > rng.end:
            raise ValidationError(
                f"Number range '{rng.name}' is full "
                f"({rng.start}–{rng.end})."
            )
        tn = BagNumber.objects.create(
            event=event, position=position, number_range=rng, number=n,
        )
        position.order.log_action(
            "pretix_bagnumbers.number.assigned",
            data={"number": n, "positionid": position.positionid},
        )
        return tn


def release_number(position, log=True):
    """Releases a bag number (e.g. on cancellation)."""
    tn = BagNumber.objects.filter(position=position).first()
    if tn is None:
        return
    number = tn.number
    tn.delete()
    if log:
        position.order.log_action(
            "pretix_bagnumbers.number.released",
            data={"number": number, "positionid": position.positionid},
        )


def sync_number(position):
    """
    Ensures the position has the correct bag number for its current product.

    - Product has no config → release any existing number.
    - Product has a config, position has no number → assign one.
    - Product has a config, position has a number from the WRONG range
      (e.g. after a product change) → release old, assign new.
    - Product has a config, position has a number from the correct range → no-op.
    """
    try:
        expected_range = position.item.bagnumber_config.number_range
    except ItemNumberConfig.DoesNotExist:
        release_number(position)
        return

    existing = BagNumber.objects.filter(position=position).first()
    if existing is None:
        assign_number(position)
    elif existing.number_range_id != expected_range.pk:
        release_number(position)
        assign_number(position)
    # else: number is already in the correct range — no-op
