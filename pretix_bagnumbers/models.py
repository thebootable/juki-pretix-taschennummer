from django.db import models


class NumberRange(models.Model):
    """
    Ein Nummernkreis, z. B. "Kinder" ab 100, "Betreuer" ab 200.
    """
    event = models.ForeignKey(
        "pretixbase.Event", on_delete=models.CASCADE,
        related_name="bagnumber_ranges",
    )
    name = models.CharField(max_length=190)
    start = models.PositiveIntegerField()
    # Optionales Ende, um Überläufe in den nächsten Kreis zu verhindern.
    # None = offen (dann schützt nur der UniqueConstraint vor Kollisionen).
    end = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = (("event", "name"),)
        ordering = ("start",)

    def __str__(self):
        return f"{self.name} (ab {self.start})"


class ItemNumberConfig(models.Model):
    """
    Zuordnung Produkt -> Nummernkreis. Produkte ohne Eintrag bekommen
    keine Nummer.
    """
    item = models.OneToOneField(
        "pretixbase.Item", on_delete=models.CASCADE,
        related_name="bagnumber_config",
    )
    number_range = models.ForeignKey(
        NumberRange, on_delete=models.CASCADE, related_name="items",
    )


class BagNumber(models.Model):
    """
    Eine vergebene Nummer. Wird bei Stornierung gelöscht (= freigegeben),
    die Lücke wird bei der nächsten Vergabe wieder aufgefüllt.
    """
    event = models.ForeignKey(
        "pretixbase.Event", on_delete=models.CASCADE,
        related_name="bagnumbers",
    )
    position = models.OneToOneField(
        "pretixbase.OrderPosition", on_delete=models.CASCADE,
        related_name="bagnumber",
    )
    number_range = models.ForeignKey(
        NumberRange, on_delete=models.PROTECT, related_name="numbers",
    )
    number = models.PositiveIntegerField()

    class Meta:
        constraints = [
            # Harte Garantie: keine Nummer zweimal pro Event,
            # auch bei manueller Änderung im Backend.
            models.UniqueConstraint(
                fields=["event", "number"],
                name="uniq_bagnumber_per_event",
            ),
        ]
        ordering = ("number",)

    def __str__(self):
        return str(self.number)
