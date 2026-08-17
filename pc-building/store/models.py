from django.db import models
from django.utils.text import slugify


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class ComponentType(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products', null=True, blank=True)
    is_active = models.BooleanField(default=True)

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

    grade = models.CharField(choices=GRADE_CHOICES, max_length=5, blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class SpecDetails(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specs')
    key = models.CharField(max_length=30)
    value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.product} - {self.key}: {self.value}"
