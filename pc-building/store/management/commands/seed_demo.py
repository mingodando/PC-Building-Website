from decimal import Decimal

from django.core.management.base import BaseCommand

from store.models import Category, Product, SpecDetails

# (category, name, price, compare_price, stock, condition, grade, featured, description, specs)
DEMO_PRODUCTS = [
    ('Graphics Card', 'NVIDIA GeForce RTX 4070 SUPER 12GB', 21900, 23900, 6, 'new', None, True,
     'Smooth 1440p gaming with DLSS 3 and ray tracing.',
     [('Memory', '12GB GDDR6X'), ('Boost Clock', '2475 MHz'), ('Power', '220W'), ('Outputs', '3× DP 1.4a, 1× HDMI 2.1')]),
    ('Graphics Card', 'AMD Radeon RX 6700 XT 12GB', 8900, 10500, 2, 'refurbished', 'A', True,
     'A 1440p workhorse, cleaned and stress-tested for 24 hours.',
     [('Memory', '12GB GDDR6'), ('Boost Clock', '2581 MHz'), ('Power', '230W')]),
    ('CPU', 'AMD Ryzen 7 7800X3D', 14500, None, 8, 'new', None, True,
     '8 cores with 3D V-Cache. One of the fastest gaming CPUs available.',
     [('Socket', 'AM5'), ('Cores / Threads', '8 / 16'), ('Boost Clock', '5.0 GHz'), ('L3 Cache', '96MB'), ('TDP', '120W')]),
    ('CPU', 'Intel Core i5-12400F', 3290, 3990, 3, 'refurbished', 'B', False,
     'Great value 6-core for budget builds.',
     [('Socket', 'LGA1700'), ('Cores / Threads', '6 / 12'), ('Boost Clock', '4.4 GHz'), ('TDP', '65W')]),
    ('RAM', 'Corsair Vengeance 32GB (2×16GB) DDR5-6000', 3690, 4290, 12, 'new', None, True,
     'Low-latency DDR5 kit tuned for AM5 and Intel 13th/14th gen.',
     [('Capacity', '32GB (2×16GB)'), ('Type', 'DDR5'), ('Speed', '6000 MT/s'), ('Latency', 'CL30')]),
    ('SSD', 'Samsung 990 PRO 2TB NVMe', 5490, None, 0, 'new', None, False,
     'PCIe 4.0 flagship SSD with up to 7,450 MB/s reads.',
     [('Capacity', '2TB'), ('Interface', 'PCIe 4.0 x4 NVMe'), ('Read', '7450 MB/s'), ('Write', '6900 MB/s')]),
    ('PSU', 'Seasonic Focus GX-750 80+ Gold', 3990, None, 5, 'new', None, False,
     'Fully modular, quiet and backed by a 10-year warranty.',
     [('Wattage', '750W'), ('Efficiency', '80+ Gold'), ('Modular', 'Fully')]),
    ('Case', 'Lian Li LANCOOL 216', 3290, 3590, 4, 'new', None, False,
     'High-airflow mid-tower with two 160mm front fans included.',
     [('Form Factor', 'Mid-tower ATX'), ('Included Fans', '2× 160mm, 1× 140mm'), ('GPU Clearance', '392mm')]),
    ('Case Fans', 'ARCTIC P12 PWM PST (5-pack)', 990, None, 20, 'new', None, False,
     'Quiet, static-pressure fans that daisy-chain on a single header.',
     [('Size', '120mm'), ('Speed', '200–1800 RPM'), ('Connector', '4-pin PWM')]),
]


class Command(BaseCommand):
    help = "Add sample products for local development. Products that already exist (by name) are skipped."

    def handle(self, *args, **options):
        created = 0
        for (category_name, name, price, compare, stock, condition, grade, featured, description, specs) in DEMO_PRODUCTS:
            if Product.objects.filter(name=name).exists():
                continue
            category, _ = Category.objects.get_or_create(name=category_name)
            product = Product.objects.create(
                name=name,
                category=category,
                price=Decimal(price),
                compare_price=Decimal(compare) if compare else None,
                stock=stock,
                condition=condition,
                grade=grade,
                is_featured=featured,
                description=description,
            )
            SpecDetails.objects.bulk_create(SpecDetails(product=product, key=k, value=v) for k, v in specs)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Added {created} demo product(s)."))
