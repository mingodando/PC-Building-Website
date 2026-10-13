from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
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

    def test_junk_quantities_are_ignored(self):
        self.login()
        self.client.post(reverse('cart_add', args=[self.gpu.pk]), {'quantity': 2})
        item = CartItem.objects.get()
        for junk in ('-5', 'abc', '1.5', ''):
            self.client.post(reverse('cart_update', args=[item.pk]), {'quantity': junk})
            item.refresh_from_db()
            self.assertEqual(item.quantity, 2)
        self.client.post(reverse('cart_update', args=[item.pk]), {'quantity': '0'})
        self.assertFalse(CartItem.objects.exists())

    def test_updating_sold_out_item_removes_it(self):
        self.login()
        self.client.post(reverse('cart_add', args=[self.gpu.pk]), {'quantity': 2})
        Product.objects.filter(pk=self.gpu.pk).update(stock=0)
        item = CartItem.objects.get()
        self.client.post(reverse('cart_update', args=[item.pk]), {'quantity': 1})
        self.assertFalse(CartItem.objects.exists())

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

    def test_product_removed_before_checkout(self):
        Product.objects.filter(pk=self.gpu.pk).update(is_active=False)
        response = self.client.post(reverse('checkout'), self.checkout_data(), follow=True)
        self.assertContains(response, 'RTX 4060 is no longer available')
        self.assertFalse(Order.objects.exists())

    def test_invalid_form_shows_errors(self):
        response = self.client.post(reverse('checkout'), self.checkout_data(postal_code='abc'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Postal codes are 5 digits.')
        self.assertContains(response, 'Please fix the highlighted fields')
        self.assertFalse(Order.objects.exists())

    def test_tampered_choices_are_rejected(self):
        response = self.client.post(reverse('checkout'), self.checkout_data(delivery_method='teleport', payment_method='crypto'))
        self.assertEqual(response.status_code, 200)
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


class AdminTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='buyer', password='pass12345!')
        self.client.post(reverse('cart_add', args=[self.gpu.pk]), {'quantity': 2})
        self.client.post(reverse('checkout'), self.checkout_data())
        self.order = Order.objects.get()
        User.objects.create_superuser('boss', 'boss@example.com', 'pass12345!')
        self.client.login(username='boss', password='pass12345!')

    def change_status(self, status):
        url = reverse('admin:store_order_change', args=[self.order.pk])
        data = {
            'user': self.user.pk, 'status': status, 'payment_method': 'promptpay', 'delivery_method': 'standard',
            'full_name': 'Test Buyer', 'email': 'buyer@example.com', 'phone': '0812345678',
            'address': '1 Sukhumvit Rd', 'city': 'Bangkok', 'postal_code': '10110', 'notes': '',
            'items-TOTAL_FORMS': 1, 'items-INITIAL_FORMS': 1,
            'items-0-id': self.order.items.get().pk, 'items-0-order': self.order.pk,
        }
        return self.client.post(url, data)

    def test_orders_cannot_be_added_by_hand(self):
        self.assertEqual(self.client.get(reverse('admin:store_order_add')).status_code, 403)

    def test_admin_pages_load(self):
        for name in ('admin:store_order_changelist', 'admin:store_product_changelist', 'admin:store_product_add'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:store_order_change', args=[self.order.pk])).status_code, 200)

    def test_cancelling_in_admin_restocks_and_cannot_reopen(self):
        self.assertEqual(self.change_status('cancelled').status_code, 302)
        self.gpu.refresh_from_db()
        self.assertEqual(self.gpu.stock, 3)

        self.change_status('paid')
        self.order.refresh_from_db()
        self.gpu.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.gpu.stock, 3)

    def test_bulk_actions_skip_cancelled_orders(self):
        Order.objects.filter(pk=self.order.pk).update(status='cancelled')
        self.client.post(reverse('admin:store_order_changelist'), {
            'action': 'mark_paid', '_selected_action': [self.order.pk],
        })
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')


class AccountTests(TestCase):
    @override_settings(
        GOOGLE_CLIENT_ID='test-id',
        SOCIALACCOUNT_PROVIDERS={'google': {'APPS': [{'client_id': 'test-id', 'secret': 'test-secret'}]}},
    )
    def test_signup_is_google_only(self):
        response = self.client.get(reverse('signup'))
        self.assertContains(response, 'Sign up with Google')
        self.assertContains(response, 'action="/auth/google/login/?process=login"')
        self.assertNotContains(response, 'name="password1"')

    @override_settings(DEBUG=True)
    def test_signup_without_google_keys_explains_setup(self):
        self.assertContains(self.client.get(reverse('signup')), 'GOOGLE_CLIENT_ID')

    def test_setup_hint_is_hidden_from_customers(self):
        response = self.client.get(reverse('signup'))
        self.assertNotContains(response, 'GOOGLE_CLIENT_ID')
        self.assertContains(response, 'Google sign-in is unavailable')

    def test_allauth_password_pages_redirect_to_store_pages(self):
        self.assertRedirects(self.client.get('/auth/signup/'), reverse('signup'))
        self.assertRedirects(self.client.get('/auth/login/?next=/cart/'), reverse('login') + '?next=/cart/',
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/auth/password/reset/'), reverse('password_reset'))

    @override_settings(
        GOOGLE_CLIENT_ID='test-id',
        SOCIALACCOUNT_PROVIDERS={'google': {'APPS': [{'client_id': 'test-id', 'secret': 'test-secret'}]}},
    )
    def test_allauth_pages_use_store_layout(self):
        response = self.client.get('/auth/google/login/')
        self.assertContains(response, 'auth-card allauth-page')
        self.assertContains(response, 'site-header')

    def test_logged_in_user_skips_login_page(self):
        User.objects.create_user('buyer', password='pass12345!')
        self.client.login(username='buyer', password='pass12345!')
        self.assertRedirects(self.client.get(reverse('login')), reverse('product_list'))

    def test_google_only_user_has_no_change_password_link(self):
        user = User.objects.create_user('googler')
        user.set_unusable_password()
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse('product_list'))
        self.assertNotContains(response, reverse('password_change'))
        self.assertContains(response, 'Log out')

    def test_error_page_renders_standalone(self):
        self.assertIn('Something went wrong', render_to_string('500.html'))

    def test_auth_pages_render(self):
        for name in ('login', 'signup', 'password_reset'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
