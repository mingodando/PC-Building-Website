# CleanByte — PC-Building-Website
For people to find and buy my PCs.

A Django store for new and refurbished PC parts, with prices in baht.

## Features
- **Catalog:** search (by name, description or spec values), category, condition and in-stock filters, sorting and pagination
- **Product pages:** specs table, sale pricing, refurbished grades (A–C), stock levels and related products
- **Accounts:** sign up with Google, log in with Google or a password, password reset and password change
- **Cart:** add, update and remove items, with quantities capped at the stock available and a progress bar toward free delivery
- **Checkout:** delivery address, Standard (free over ฿5,000) or Express delivery, and PromptPay, bank transfer or cash on delivery. Stock is locked while the order is placed, so two buyers can't get the same last unit.
- **Orders:** confirmation page with a payment reference, a confirmation email, order history, a status tracker, and cancelling while the order is pending (this puts the stock back)
- **Admin:** product images, inline specs, stock and price editing from the product list, and bulk "mark paid / shipped / delivered" actions for orders
- Responsive layout with automatic dark mode

## Getting started
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cd pc-building
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo      # optional: adds sample products
python manage.py runserver
```
Then open http://127.0.0.1:8000. Add products at http://127.0.0.1:8000/admin/.

## Google sign-up
Customers create accounts with Google. To turn it on:

1. In the [Google Cloud console](https://console.cloud.google.com/apis/credentials), create an **OAuth client ID** of type **Web application**.
2. Add the authorized redirect URI `http://127.0.0.1:8000/auth/google/login/callback/` (and `https://yourdomain.com/auth/google/login/callback/` when you deploy).
3. Set these environment variables before `runserver`:

| Variable | Value |
| --- | --- |
| `GOOGLE_CLIENT_ID` | the client ID from step 1 |
| `GOOGLE_CLIENT_SECRET` | the client secret from step 1 |

Until they're set, the sign-up page shows a note instead of the Google button. Admin accounts made with `createsuperuser` still log in with a password.

## Taking payments
Orders start as **Pending**. When a PromptPay or bank transfer payment arrives, find the order in the admin by its `CB-XXXXXXXX` reference and mark it **Paid**, then **Shipped** and **Delivered**. Customers see each step on their order page.

To show your payment details to customers, set these environment variables:

| Variable | Example |
| --- | --- |
| `STORE_PROMPTPAY_ID` | `081-234-5678` |
| `STORE_BANK_ACCOUNT` | `Kasikorn 123-4-56789-0 (CleanByte Co.)` |

## Running tests
```bash
cd pc-building
python manage.py test store
```

## Deploying
Set these environment variables in production:

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | a long random string |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `yourdomain.com,www.yourdomain.com` |

Also run `python manage.py collectstatic`, serve `media/` through your web server, and replace the console email backend in `settings.py` (`MAILERS`) with a real SMTP backend so customers actually receive their emails.
