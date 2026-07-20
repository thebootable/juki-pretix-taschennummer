from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PluginApp(AppConfig):
    name = "pretix_bagnumbers"
    verbose_name = _("Taschennummern")

    class PretixPluginMeta:
        name = _("Taschennummern")
        author = "Tobi"
        description = _(
            "Fortlaufende Taschennummern mit konfigurierbaren Nummernkreisen "
            "pro Produkt. Nummern sind eventweit eindeutig, werden bei "
            "Stornierung wieder freigegeben und stehen auf Ticketdruck "
            "und in Exporten zur Verfügung."
        )
        visible = True
        version = "0.1.0"
        category = "FEATURE"
        compatibility = "pretix>=2024.7.0"

    def ready(self):
        from . import signals  # noqa
        from . import logentrytypes  # noqa -- Registry-Einträge laden
