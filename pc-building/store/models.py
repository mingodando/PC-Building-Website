import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def unique_slug(instance, value, max_length):
    """Slugify `value`, adding -2, -3, ... until no other row of the model uses it."""
    base = slugify(value)[:max_length] or 'item'
    slug = base
    n = 2
    model = type(instance)
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        suffix = f"-{n}"
        slug = f"{base[:max_length - len(suffix)]}{suffix}"
        n += 1
    return slug


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 100)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('product_list')}?category={self.slug}"


class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Original price. If higher than price, the product shows as on sale.",
    )
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show this product on the home page.")
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('refurbished', 'Refurbished'),
    ]

    condition = models.CharField(choices=CONDITION_CHOICES, max_length=20, default='new')

    slug = models.SlugField(max_length=150, unique=True, blank=True)

    GRADE_CHOICES = [
        ('A', 'Grade A'),
        ('B', 'Grade B'),
        ('C', 'Grade C'),
    ]

    GRADE_DESCRIPTIONS = {
        'A': 'Like new. No visible marks, fully tested.',
        'B': 'Light signs of use, fully tested and working.',
        'C': 'Visible wear, fully tested and working.',
    }

    grade = models.CharField(choices=GRADE_CHOICES, max_length=5, blank=True, null=True)

    LOW_STOCK_THRESHOLD = 3

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 150)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('product_detail', args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def low_stock(self):
        return 0 < self.stock <= self.LOW_STOCK_THRESHOLD

    @property
    def on_sale(self):
        return self.compare_price is not None and self.compare_price > self.price

    @property
    def savings(self):
        return self.compare_price - self.price if self.on_sale else 0

    @property
    def discount_percent(self):
        if not self.on_sale:
            return 0
        return int(round((1 - self.price / self.compare_price) * 100))

    @property
    def grade_description(self):
        return self.GRADE_DESCRIPTIONS.get(self.grade, '')


class SpecDetails(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specs')
    key = models.CharField(max_length=30)
    value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.product} - {self.key}: {self.value}"

    class Meta:
        verbose_name_plural = "Spec Details"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart of {self.user.username}"

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.subtotal for item in self.items.all()), Decimal('0'))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.product} x {self.quantity} in {self.cart}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    DELIVERY_CHOICES = [
        ('standard', 'Standard Delivery'),
        ('express', 'Express Delivery'),
    ]

    # Fee in baht, and the order subtotal at which it becomes free (None = never free).
    DELIVERY_FEES = {
        'standard': (Decimal('100'), Decimal('5000')),
        'express': (Decimal('250'), None),
    }

    DELIVERY_ETA = {
        'standard': '3–5 business days',
        'express': '1–2 business days',
    }

    PAYMENT_CHOICES = [
        ('promptpay', 'PromptPay'),
        ('bank_transfer', 'Bank Transfer'),
        ('cod', 'Cash on Delivery'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(choices=STATUS_CHOICES, max_length=20, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True, null=True, unique=True)
    payment_method = models.CharField(choices=PAYMENT_CHOICES, max_length=20, default='promptpay')
    delivery_method = models.CharField(choices=DELIVERY_CHOICES, max_length=20, default='standard')

    full_name = models.CharField(max_length=100, default='')
    email = models.EmailField(default='')
    phone = models.CharField(max_length=20, default='')
    address = models.CharField(max_length=255, default='')
    city = models.CharField(max_length=100, default='')
    postal_code = models.CharField(max_length=10, default='')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.payment_reference:
            self.payment_reference = f"CB-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('order_detail', args=[self.pk])

    @classmethod
    def delivery_fee_for(cls, method, subtotal):
        fee, free_over = cls.DELIVERY_FEES[method]
        if free_over is not None and subtotal >= free_over:
            return Decimal('0')
        return fee

    @property
    def subtotal(self):
        return self.total_price - self.shipping_fee

    @property
    def delivery_eta(self):
        return self.DELIVERY_ETA.get(self.delivery_method, '')

    @property
    def can_cancel(self):
        return self.status == 'pending'

    @property
    def awaiting_payment(self):
        return self.status == 'pending' and self.payment_method != 'cod'

    @property
    def progress_step(self):
        """How far along the order is, for the progress tracker (0 = placed ... 3 = delivered)."""
        return {'pending': 0, 'paid': 1, 'shipped': 2, 'delivered': 3}.get(self.status, -1)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # Kept nullable so deleting a product never deletes order history.
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=100, default='')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name or self.product} x {self.quantity} in {self.order}"

    @property
    def subtotal(self):
        return self.price * self.quantity
