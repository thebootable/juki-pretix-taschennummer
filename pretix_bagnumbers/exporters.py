from django.utils.translation import gettext_lazy as _

from pretix.base.exporter import ListExporter

from .models import BagNumber


class BagNumberExporter(ListExporter):
    identifier = "bagnumbers"
    verbose_name = _("Taschennummern")

    @property
    def export_filename(self):
        return "bagnumbers"

    def iterate_list(self, form_data):
        yield [
            _("Taschennummer"), _("Nummernkreis"), _("Bestellcode"),
            _("Produkt"), _("Name"), _("Status"),
        ]
        qs = BagNumber.objects.filter(
            event=self.event
        ).select_related(
            "position__order", "position__item", "number_range"
        ).order_by("number")
        for tn in qs:
            pos = tn.position
            yield [
                tn.number,
                tn.number_range.name,
                pos.order.code,
                str(pos.item),
                pos.attendee_name or "",
                pos.order.get_status_display(),
            ]
