from django.core.exceptions import ValidationError
from django.db import transaction

from .models import BagNumber, ItemNumberConfig, NumberRange


def assign_number(position):
    """
    Vergibt die kleinste freie Nummer >= range.start für eine OrderPosition.
    Gibt None zurück, wenn das Produkt keinen Nummernkreis hat oder die
    Position bereits eine Nummer besitzt.

    Race-Condition-Schutz: Der Nummernkreis wird per SELECT ... FOR UPDATE
    gesperrt, damit zwei parallele Bestellungen nicht dieselbe Nummer ziehen.
    Der UniqueConstraint ist das zweite Sicherheitsnetz.
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
        # Eventweit belegte Nummern holen, nicht nur die des Kreises --
        # falls ein offener Kreis in den nächsten hineingelaufen ist.
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
    """
    Nummer freigeben (z. B. bei Stornierung).
    log=False beim Löschen von Testmodus-Bestellungen, da die Bestellung
    samt Log ohnehin verschwindet.
    """
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


