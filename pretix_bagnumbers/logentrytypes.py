from django.utils.translation import gettext_lazy as _

from pretix.base.logentrytypes import OrderLogEntryType, log_entry_types


@log_entry_types.new_from_dict({
    "pretix_bagnumbers.number.assigned": _(
        "Taschennummer {number} wurde vergeben (Position #{positionid})."
    ),
    "pretix_bagnumbers.number.released": _(
        "Taschennummer {number} wurde freigegeben (Position #{positionid})."
    ),
    "pretix_bagnumbers.number.changed": _(
        "Taschennummer wurde manuell von {old_number} auf {number} "
        "geändert (Position #{positionid})."
    ),
})
class BagNumberLogEntryType(OrderLogEntryType):
    # Eigene Subklasse ist Pflicht, damit die Registry die Einträge
    # diesem Plugin zuordnen kann.
    pass
