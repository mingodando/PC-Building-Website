from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Cart, CartItem, Category, Order, Product
from .templatetags.store_extras import baht


# Create your tests here.
class StoreTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Graphics Card')
        self.gpu = Product.objects.create(name='RTX 4060', category=self.category, price=Decimal('10000'), stock=3)
        self.user = User.objects.create_user('buyer', 'buyer@example.com', 'pass12345!')

    def login(self):
        self.client.login(username='buyer', password='pass12345!')

    def checkout_data(self, **overrides):
        data = {
            'full_name': 'Test Buyer', 'email': 'buyer@example.com', 'phone': '0812345678',
            'address': '1 Sukhumvit Rd', 'city': 'Bangkok', 'postal_code': '10110',
            'delivery_method': 'standard', 'payment_method': 'promptpay', 'notes': '',
        }
        data.update(overrides)
        return data


class ModelTests(StoreTestCase):
    def test_slugs_are_unique(self):
        other = Product.objects.create(name='RTX 4060', category=self.category, price=1)
        self.assertEqual(self.gpu.slug, 'rtx-4060')
        self.assertEqual(other.slug, 'rtx-4060-2')

    def test_sale_and_discount(self):
        self.gpu.compare_price = Decimal('12500')
        self.assertTrue(self.gpu.on_sale)
        self.assertEqual(self.gpu.discount_percent, 20)
        self.assertEqual(self.gpu.savings, Decimal('2500'))

    def test_free_standard_delivery_over_threshold(self):
        self.assertEqual(Order.delivery_fee_for('standard', Decimal('4999')), Decimal('100'))
        self.assertEqual(Order.delivery_fee_for('standard', Decimal('5000')), 0)
        self.assertEqual(Order.delivery_fee_for('express', Decimal('99999')), Decimal('250'))

    def test_baht_filter(self):
        self.assertEqual(baht(Decimal('15000.00')), '฿15,000')
        self.assertEqual(baht(Decimal('99.5')), '฿99.50')


class CatalogTests(StoreTestCase):
    def test_list_search_and_filter(self):
        Product.objects.create(name='Ryzen 5 7600', category=Category.objects.create(name='CPU'), price=6000, stock=1)
        response = self.client.get(reverse('product_list'))
        self.assertContains(response, 'RTX 4060')
        self.assertContains(response, 'Ryzen 5 7600')

        response = self.client.get(reverse('product_list'), {'q': 'ryzen'})
        self.assertNotContains(response, 'RTX 4060')
        self.assertContains(response, 'Ryzen 5 7600')

        response = self.client.get(reverse('product_list'), {'category': 'graphics-card'})
        self.assertContains(response, 'RTX 4060')
        self.assertNotContains(response, 'Ryzen 5 7600')

    def test_inactive_product_is_hidden(self):
        self.gpu.is_active = False
        self.gpu.save()
        self.assertEqual(self.client.get(self.gpu.get_absolute_url()).status_code, 404)

    def test_detail_page(self):
        response = self.client.get(self.gpu.get_absolute_url())
        self.assertContains(response, '฿10,000')
        self.assertContains(response, 'Add to cart')


class CartTests(StoreTestCase):
    def test_anonymous_add_redirects_to_login(self):
        response = self.client.post(reverse('cart_add', args=[self.gpu.pk]))
        self.assertRedirects(response, f"{reverse('login')}?next={self.gpu.get_absolute_url()}")

    def test_add_update_remove(self):
        self.login()
        self.client.post(reverse('cart_add', args=[self.gpu.pk]), {'quantity': 2})
        item = CartItem.objects.get(cart__user=self.user)
        self.assertEqual(item.quantity, 2)

        self.client.post(reverse('cart_update', args=[item.pk]), {'quantity': 1})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

        self.client.post(reverse('cart_remove', args=[item.pk]))
        self.assertFalse(CartItem.objects.exists())

    def test_add_is_capped_at_stock(self):
        self.login()
        self.client.post(reverse('cart_add', args=[self.gpu.pk]), {'quantity': 10})
        self.assertEqual(CartItem.objects.get().quantity, 3)

    def test_cannot_touch_someone_elses_cart(self):
        other = User.objects.create_user('other', password='pass12345!')
        item = CartItem.objects.create(cart=Cart.objects.create(user=other), product=self.gpu, quantity=1)
        self.login()
        self.assertEqual(self.client.post(reverse('cart_remove', args=[item.pk])).status_code, 404)


class CheckoutTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.client.post(reverse('cart_add', args=[self.gpu.pk]), {'quantity': 2})

    def test_place_order(self):
        response = self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get()
        self.assertRedirects(response, f"{order.get_absolute_url()}?placed=1")
        self.assertEqual(order.total_price, Decimal('20000'))
        self.assertEqual(order.shipping_fee, 0)
        self.assertTrue(order.payment_reference.startswith('CB-'))
        self.assertEqual(order.items.get().product_name, 'RTX 4060')

        self.gpu.refresh_from_db()
        self.assertEqual(self.gpu.stock, 1)
        self.assertFalse(CartItem.objects.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.payment_reference, mail.outbox[0].body)

    def test_express_fee_is_added(self):
        self.client.post(reverse('checkout'), self.checkout_data(delivery_method='express'))
        self.assertEqual(Order.objects.get().total_price, Decimal('20250'))

    def test_stock_ran_out_before_checkout(self):
        Product.objects.filter(pk=self.gpu.pk).update(stock=1)
        response = self.client.post(reverse('checkout'), self.checkout_data())
        self.assertRedirects(response, reverse('cart_detail'))
        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.exists())

    def test_invalid_form_shows_errors(self):
        response = self.client.post(reverse('checkout'), self.checkout_data(postal_code='abc'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Postal codes are 5 digits.')
        self.assertFalse(Order.objects.exists())

    def test_cancel_restores_stock(self):
        self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get()
        self.client.post(reverse('order_cancel', args=[order.pk]))
        order.refresh_from_db()
        self.gpu.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(self.gpu.stock, 3)

    def test_orders_are_private(self):
        self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get()
        User.objects.create_user('snoop', password='pass12345!')
        self.client.login(username='snoop', password='pass12345!')
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)


class AccountTests(TestCase):
    def test_signup_logs_in(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newbie', 'email': 'new@example.com',
            'password1': 'Sup3r-secret-pw', 'password2': 'Sup3r-secret-pw',
        })
        self.assertRedirects(response, reverse('product_list'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newbie').pk)

    def test_auth_pages_render(self):
        for name in ('login', 'signup', 'password_reset'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
