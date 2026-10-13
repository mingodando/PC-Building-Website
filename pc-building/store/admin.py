from django.contrib import admin, messages
from django.db import transaction
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

    def has_add_permission(self, request, obj=None):
        return False


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

    def has_add_permission(self, request):
        # Orders come from checkout, which works out totals and takes the stock.
        return False

    def save_model(self, request, obj, form, change):
        old_status = Order.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        if old_status == 'cancelled' and obj.status != 'cancelled':
            obj.status = 'cancelled'
            self.message_user(
                request, f"Order #{obj.pk} was cancelled and its stock returned, so it can't be reopened.",
                messages.WARNING,
            )
        if obj.status == 'cancelled' and old_status not in (None, 'cancelled'):
            with transaction.atomic():
                super().save_model(request, obj, form, change)
                obj.cancel()
            return
        super().save_model(request, obj, form, change)

    def _set_status(self, request, queryset, status):
        updated = queryset.exclude(status='cancelled').update(status=status)
        skipped = queryset.count() - updated
        self.message_user(request, f"Marked {updated} order{'s' if updated != 1 else ''} as {status}.")
        if skipped:
            self.message_user(request, f"Skipped {skipped} cancelled order{'s' if skipped != 1 else ''}.", messages.WARNING)

    @admin.action(description='Mark selected orders as paid')
    def mark_paid(self, request, queryset):
        self._set_status(request, queryset, 'paid')

    @admin.action(description='Mark selected orders as shipped')
    def mark_shipped(self, request, queryset):
        self._set_status(request, queryset, 'shipped')

    @admin.action(description='Mark selected orders as delivered')
    def mark_delivered(self, request, queryset):
        self._set_status(request, queryset, 'delivered')
