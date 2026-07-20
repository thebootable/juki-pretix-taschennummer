from django.utils.translation import gettext_lazy as _

from pretix.base.logentrytypes import OrderLogEntryType, log_entry_types


@log_entry_types.new_from_dict({
    "pretix_bagnumbers.number.assigned": _(
        "Bag number {number} was assigned (position #{positionid})."
    ),
    "pretix_bagnumbers.number.released": _(
        "Bag number {number} was released (position #{positionid})."
    ),
    "pretix_bagnumbers.number.changed": _(
        "Bag number was manually changed from {old_number} to {number} "
        "(position #{positionid})."
    ),
})
class BagNumberLogEntryType(OrderLogEntryType):
    pass
