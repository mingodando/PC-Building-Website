from django.conf import settings

from .models import Category, CartItem


def store(request):
    """Values every page needs: the nav categories and the cart badge count."""
    cart_count = 0
    if request.user.is_authenticated:
        cart_count = sum(
            CartItem.objects.filter(cart__user=request.user).values_list('quantity', flat=True)
        )
    return {
        'store_name': settings.STORE_NAME,
        'nav_categories': Category.objects.all(),
        'cart_count': cart_count,
        'google_enabled': bool(settings.GOOGLE_CLIENT_ID),
        'debug': settings.DEBUG,
    }
