from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, SpecDetails, Cart, CartItem, Order, OrderItem


# Register your models here.
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class SpecDetailsInline(admin.TabularInline):
    model = SpecDetails
    extra = 3


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('thumbnail', 'name', 'category', 'price', 'stock', 'condition', 'grade', 'is_active', 'is_featured')
    list_display_links = ('thumbnail', 'name')
    list_editable = ('price', 'stock', 'is_active', 'is_featured')
    list_filter = ('category', 'condition', 'grade', 'is_active', 'is_featured')
    search_fields = ('name', 'description', 'specs__value')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SpecDetailsInline]
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'category', 'description', 'image')}),
        ('Pricing & stock', {'fields': ('price', 'compare_price', 'stock')}),
        ('Condition', {'fields': ('condition', 'grade')}),
        ('Visibility', {'fields': ('is_active', 'is_featured')}),
    )

    @admin.display(description='')
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:40px;height:40px;object-fit:cover;border-radius:6px">', obj.image.url)
        return '—'


@admin.register(SpecDetails)
class SpecDetailsAdmin(admin.ModelAdmin):
    list_display = ('product', 'key', 'value')
    search_fields = ('product__name', 'key', 'value')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    inlines = [CartItemInline]


admin.site.register(CartItem)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'quantity', 'price')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment_reference', 'full_name', 'user', 'created_at', 'total_price', 'payment_method', 'delivery_method', 'status')
    list_editable = ('status',)
    list_filter = ('status', 'payment_method', 'delivery_method', 'created_at')
    search_fields = ('payment_reference', 'full_name', 'email', 'phone', 'user__username')
    readonly_fields = ('created_at', 'payment_reference', 'total_price', 'shipping_fee')
    inlines = [OrderItemInline]
    actions = ['mark_paid', 'mark_shipped', 'mark_delivered']
    fieldsets = (
        (None, {'fields': ('user', 'status', 'created_at', 'payment_reference')}),
        ('Payment', {'fields': ('payment_method', 'total_price', 'shipping_fee')}),
        ('Delivery', {'fields': ('delivery_method', 'full_name', 'email', 'phone', 'address', 'city', 'postal_code', 'notes')}),
    )

    @admin.action(description='Mark selected orders as paid')
    def mark_paid(self, request, queryset):
        queryset.update(status='paid')

    @admin.action(description='Mark selected orders as shipped')
    def mark_shipped(self, request, queryset):
        queryset.update(status='shipped')

    @admin.action(description='Mark selected orders as delivered')
    def mark_delivered(self, request, queryset):
        queryset.update(status='delivered')
