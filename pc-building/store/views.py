import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import CheckoutForm
from .models import Cart, CartItem, Category, Order, OrderItem, Product

logger = logging.getLogger(__name__)

SORT_OPTIONS = {
    'newest': ('Newest', '-created_at'),
    'price_asc': ('Price: low to high', 'price'),
    'price_desc': ('Price: high to low', '-price'),
    'name': ('Name', 'name'),
}


# Create your views here.
def product_list(request):
    products = Product.objects.filter(is_active=True).select_related('category')

    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '')
    condition = request.GET.get('condition', '')
    in_stock_only = request.GET.get('in_stock') == '1'
    sort = request.GET.get('sort', 'newest')
    if sort not in SORT_OPTIONS:
        sort = 'newest'

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(specs__value__icontains=query)
        ).distinct()

    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        if active_category:
            products = products.filter(category=active_category)

    if condition in dict(Product.CONDITION_CHOICES):
        products = products.filter(condition=condition)
    else:
        condition = ''

    if in_stock_only:
        products = products.filter(stock__gt=0)

    products = products.order_by(SORT_OPTIONS[sort][1])

    page = Paginator(products, 12).get_page(request.GET.get('page'))

    is_filtered = bool(query or active_category or condition or in_stock_only)
    show_hero = not is_filtered and page.number == 1

    categories = Category.objects.annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    ).filter(product_count__gt=0)

    featured = []
    if show_hero:
        featured = Product.objects.filter(is_active=True, is_featured=True).select_related('category')[:4]

    return render(request, 'store/product_list.html', {
        'page': page,
        'products': page.object_list,
        'categories': categories,
        'featured': featured,
        'query': query,
        'active_category': active_category,
        'condition': condition,
        'in_stock_only': in_stock_only,
        'sort': sort,
        'sort_options': [(key, label) for key, (label, _) in SORT_OPTIONS.items()],
        'condition_options': Product.CONDITION_CHOICES,
        'is_filtered': is_filtered,
        'show_hero': show_hero,
        'total_count': page.paginator.count,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('specs'),
        slug=slug, is_active=True,
    )
    related = (
        Product.objects.filter(is_active=True, category=product.category)
        .exclude(pk=product.pk)
        .select_related('category')[:4]
    )
    in_cart = 0
    if request.user.is_authenticated:
        item = CartItem.objects.filter(cart__user=request.user, product=product).first()
        in_cart = item.quantity if item else 0
    return render(request, 'store/product_detail.html', {
        'product': product,
        'related': related,
        'in_cart': in_cart,
    })


# ---------- Cart ----------

def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def parse_quantity(value, default=1):
    """A whole number of at least 0 from a form value; anything else (blank, negative, 1.5) gives `default`."""
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return default
    return quantity if quantity >= 0 else default


@login_required
def cart_detail(request):
    cart = get_cart(request.user)
    items = list(cart.items.select_related('product', 'product__category'))
    subtotal = sum((item.subtotal for item in items), 0)
    standard_fee = Order.delivery_fee_for('standard', subtotal)
    free_over = Order.DELIVERY_FEES['standard'][1]
    return render(request, 'store/cart.html', {
        'items': items,
        'subtotal': subtotal,
        'standard_fee': standard_fee,
        'estimated_total': subtotal + standard_fee,
        'free_shipping_remaining': max(free_over - subtotal, 0),
        'free_shipping_progress': min(int(subtotal / free_over * 100), 100) if free_over else 100,
        'has_stock_problem': any(item.quantity > item.product.stock or not item.product.is_active for item in items),
    })


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    if not request.user.is_authenticated:
        messages.info(request, "Log in or create an account to start your cart.")
        return redirect_to_login(product.get_absolute_url())

    quantity = parse_quantity(request.POST.get('quantity'), 1) or 1
    cart = get_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 0})
    wanted = item.quantity + quantity

    if product.stock == 0:
        if created:
            item.delete()
        messages.error(request, f"Sorry, {product.name} is out of stock.")
        return redirect(product.get_absolute_url())

    if wanted > product.stock:
        wanted = product.stock
        messages.warning(request, f"Only {product.stock} of {product.name} available, so your cart has the maximum.")
    else:
        messages.success(request, f"Added {product.name} to your cart.")
    item.quantity = wanted
    item.save()

    if request.POST.get('next') == 'cart':
        return redirect('cart_detail')
    return redirect(product.get_absolute_url())


@login_required
@require_POST
def cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    quantity = parse_quantity(request.POST.get('quantity'), item.quantity)
    if quantity == 0 or item.product.stock == 0 or not item.product.is_active:
        name = item.product.name
        item.delete()
        messages.success(request, f"Removed {name} from your cart.")
    else:
        if quantity > item.product.stock:
            quantity = item.product.stock
            messages.warning(request, f"Only {item.product.stock} of {item.product.name} available.")
        item.quantity = quantity
        item.save()
    return redirect('cart_detail')


@login_required
@require_POST
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    name = item.product.name
    item.delete()
    messages.success(request, f"Removed {name} from your cart.")
    return redirect('cart_detail')


# ---------- Checkout & orders ----------

class StockError(Exception):
    pass


def place_order(user, cart, form):
    """Turn the cart into an order. Locks the products so two buyers can't take the same last unit."""
    with transaction.atomic():
        items = list(cart.items.select_related('product'))
        products = {
            p.pk: p for p in Product.objects.select_for_update().filter(pk__in=[i.product_id for i in items])
        }
        for item in items:
            product = products[item.product_id]
            if not product.is_active or item.quantity > product.stock:
                raise StockError(product)

        subtotal = sum((products[i.product_id].price * i.quantity for i in items), 0)
        order = form.save(commit=False)
        order.user = user
        order.shipping_fee = Order.delivery_fee_for(order.delivery_method, subtotal)
        order.total_price = subtotal + order.shipping_fee
        order.save()

        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=products[i.product_id],
                product_name=products[i.product_id].name,
                quantity=i.quantity,
                price=products[i.product_id].price,
            )
            for i in items
        ])
        for item in items:
            # Only take stock that is still there, in case another order got in first (SQLite has no row locks).
            taken = Product.objects.filter(pk=item.product_id, stock__gte=item.quantity).update(
                stock=F('stock') - item.quantity
            )
            if not taken:
                raise StockError(Product.objects.get(pk=item.product_id))
        cart.items.all().delete()
    return order


def send_order_email(order):
    context = {'order': order, 'items': order.items.all(), 'store_name': settings.STORE_NAME,
               'promptpay_id': settings.STORE_PROMPTPAY_ID, 'bank_account': settings.STORE_BANK_ACCOUNT}
    try:
        send_mail(
            subject=f"{settings.STORE_NAME} order #{order.pk} confirmed",
            message=render_to_string('store/emails/order_confirmation.txt', context),
            from_email=None,
            recipient_list=[order.email],
        )
    except Exception:
        # The order is already placed; a mail outage shouldn't show the customer an error page.
        logger.exception("Could not send confirmation email for order %s", order.pk)


@login_required
def checkout(request):
    cart = get_cart(request.user)
    items = list(cart.items.select_related('product', 'product__category'))
    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect('cart_detail')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = place_order(request.user, cart, form)
            except StockError as exc:
                product = exc.args[0]
                if product.is_active and product.stock:
                    problem = f"only has {product.stock} left"
                else:
                    problem = "is no longer available"
                messages.error(request, f"Sorry, {product.name} {problem}. Please update your cart.")
                return redirect('cart_detail')
            send_order_email(order)
            return redirect(f"{order.get_absolute_url()}?placed=1")
    else:
        last_order = request.user.orders.first()
        initial = {'email': request.user.email, 'full_name': request.user.get_full_name()}
        if last_order:
            initial.update({
                field: getattr(last_order, field)
                for field in ('full_name', 'email', 'phone', 'address', 'city', 'postal_code')
            })
        form = CheckoutForm(initial=initial)

    subtotal = sum((item.subtotal for item in items), 0)
    delivery_options = [
        {
            'value': value,
            'label': label,
            'fee': Order.delivery_fee_for(value, subtotal),
            'eta': Order.DELIVERY_ETA[value],
        }
        for value, label in Order.DELIVERY_CHOICES
    ]
    selected_delivery = form['delivery_method'].value()
    if selected_delivery not in Order.DELIVERY_FEES:
        selected_delivery = 'standard'
    shipping_fee = Order.delivery_fee_for(selected_delivery, subtotal)
    return render(request, 'store/checkout.html', {
        'form': form,
        'items': items,
        'subtotal': subtotal,
        'delivery_options': delivery_options,
        'selected_delivery': selected_delivery,
        'shipping_fee': shipping_fee,
        'total': subtotal + shipping_fee,
    })


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related('items')
    return render(request, 'store/order_list.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), pk=order_id, user=request.user)
    return render(request, 'store/order_detail.html', {
        'order': order,
        'just_placed': request.GET.get('placed') == '1',
        'promptpay_id': settings.STORE_PROMPTPAY_ID,
        'bank_account': settings.STORE_BANK_ACCOUNT,
        'steps': ['Placed', 'Paid', 'Shipped', 'Delivered'],
    })


@login_required
@require_POST
def order_cancel(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id, user=request.user)
        if not order.can_cancel:
            messages.error(request, "This order can no longer be cancelled. Contact us if you need help.")
            return redirect(order)
        order.cancel()
    messages.success(request, f"Order #{order.pk} has been cancelled.")
    return redirect(order)


# ---------- Accounts ----------

def signup(request):
    """Sign-up happens through Google (django-allauth); this page just offers the button."""
    if request.user.is_authenticated:
        return redirect('product_list')
    next_url = request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        next_url = ''
    return render(request, 'registration/signup.html', {'next': next_url})
