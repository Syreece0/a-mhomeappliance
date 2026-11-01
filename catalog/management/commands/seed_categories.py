from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category

TREE = {
    "Kitchen Appliances": [
        "Blenders", "Microwaves", "Electric kettles", "Toasters", "Sandwich makers", "Rice cookers", "Air fryers",
        "Food processors", "Coffee makers", "Hand mixers", "Electric cookers", "Gas cookers", "Ovens", "Deep fryers",
    ],
    "Refrigeration": ["Refrigerators", "Deep freezers", "Chest freezers", "Display refrigerators"],
    "Laundry Appliances": [
        "Washing machines", "Spin dryers", "Drying machines", "Electric irons", "Steam irons", "Clothes steamers",
        "Ironing boards",
    ],
    "Cooling and Heating": [
        "Standing fans", "Table fans", "Ceiling fans", "Wall fans", "Air conditioners", "Air coolers",
        "Electric heaters", "Water heaters", "Air purifiers",
    ],
    "Television and Entertainment": [
        "Smart televisions", "Home theatres", "Soundbars", "Bluetooth speakers", "Radios", "Projectors", "Decoders",
        "Gaming consoles",
    ],
    "Home Essentials": [
        "Rechargeable lamps", "Emergency lights", "Extension boxes", "Voltage stabilizers", "UPS", "Electric sockets",
        "LED bulbs", "Batteries", "Rechargeable fans", "Water dispensers",
    ],
    "Personal Care Appliances": [
        "Hair dryers", "Hair clippers", "Electric shavers", "Electric toothbrushes", "Hair styling appliances",
    ],
    "Cooking Appliances": ["Gas cookers", "Electric cookers", "Ovens", "Electric grills", "Hot plates"],
}


class Command(BaseCommand):
    help = "Create the A&M product category tree (safe to re-run; existing categories are left untouched)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for p_pos, (parent_name, children) in enumerate(TREE.items()):
            parent, was_new = Category.objects.get_or_create(
                name=parent_name, parent=None, defaults={"position": p_pos}
            )
            created += was_new
            for c_pos, child in enumerate(children):
                _, was_new = Category.objects.get_or_create(name=child, parent=parent, defaults={"position": c_pos})
                created += was_new
        self.stdout.write(self.style.SUCCESS(f"Categories ready ({created} created)."))
