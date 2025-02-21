from decimal import Decimal
import stripe
import uuid

from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings

from yookassa import Configuration, Payment

from cart.cart import Cart

from .forms import ShippingAddressForm
from .models import Order, OrderItem, ShippingAddress

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = settings.STRIPE_API_VERSION

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

@login_required(login_url='accountlogin')
def shipping(request):
    try:
        shipping_address = ShippingAddress.objects.get(user=request.user)
    except ShippingAddress.DoesNotExist:
        shipping_address = None
    form = ShippingAddressForm(instance=shipping_address)

    if request.method == 'POST':
        form = ShippingAddressForm(request.POST, instance=shipping_address)
        if form.is_valid():
            shipping_address = form.save(commit=False)
            shipping_address.user = request.user
            shipping_address.save()
            return redirect('account:dashboard')

    return render(request, 'payment/shipping.html', {'form': form})

def checkout(request):
    if request.user.is_authenticated:
        shipping_address, _ = ShippingAddress.objects.get_or_create(
            user=request.user)
        return render(request, 'payment/checkout.html', {'shipping_address': shipping_address})
    return render(request, 'payment/checkout.html')






def complete_order(request):
    if request.method == 'POST':

        payment_type = request.POST.get('stripe-payment', 'yookassa-payment')

        name = request.POST.get('name')
        email = request.POST.get('email')
        street_address = request.POST.get('street_address')
        apartment_address = request.POST.get('apartment_address')
        country = request.POST.get('country')
        zip = request.POST.get('zipcode')
        cart = Cart(request)
        total_price = cart.get_total_price()

        match payment_type:
            case "stripe-payment":

                shipping_address, _ = ShippingAddress.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'name': name,
                        'email': email,
                        'street_address': street_address,
                        'apartment_address': apartment_address,
                        'country': country,
                        'zip': zip
                    }
                )
                session_data = {
                    'mode': 'payment',
                    'success_url': request.build_absolute_uri(reverse('payment:payment-success')),
                    'cancel_url': request.build_absolute_uri(reverse('payment:payment-fail')),
                    'line_items': []
                }

                if request.user.is_authenticated:
                    order = Order.objects.create(
                        user=request.user, shipping_address=shipping_address, amount=total_price)

                    for item in cart:
                        OrderItem.objects.create(
                            order=order, product=item['product'], price=item['price'], quantity=item['qty'], user=request.user)

                        session_data['line_items'].append({
                            'price_data': {
                                'unit_amount': int(item['price'] * Decimal(100)),
                                'currency': 'usd',
                                'product_data': {
                                    'name': item['product']
                                },
                            },
                            'quantity': item['qty'],
                        })

                        session = stripe.checkout.Session.create(**session_data)
                        return redirect(session.url, code=303)
                else:
                    order = Order.objects.create(
                        shipping_address=shipping_address, amount=total_price)

                    for item in cart:
                        OrderItem.objects.create(
                            order=order, product=item['product'], price=item['price'], quantity=item['qty'])


            # case "yookassa-payment":
            case "yookassa-payment":
                idempotence_key = uuid.uuid4()

                currency = 'RUB'
                description = 'Товары в корзине'
                payment = Payment.create({
                    "amount": {
                        "value": str(total_price * 93),
                        "currency": currency
                    },
                    "confirmation": {
                        "type": "redirect",
                        "return_url": request.build_absolute_uri(reverse('payment:payment-success')),
                    },
                    "capture": True,
                    "test": True,
                    "description": description,
                }, idempotence_key)

                shipping_address, _ = ShippingAddress.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'name': name,
                        'email': email,
                        'street_address': street_address,
                        'apartment_address': apartment_address,
                        'country': country,
                        'zip': zip
                    }
                )

                confirmation_url = payment.confirmation.confirmation_url

                if request.user.is_authenticated:
                    order = Order.objects.create(
                        user=request.user, shipping_address=shipping_address, amount=total_price)

                    for item in cart:
                        OrderItem.objects.create(
                            order=order, product=item['product'], price=item['price'], quantity=item['qty'], user=request.user)

                    return redirect(confirmation_url)

                else:
                    order = Order.objects.create(
                        shipping_address=shipping_address, amount=total_price)

                    for item in cart:
                        OrderItem.objects.create(
                            order=order, product=item['product'], price=item['price'], quantity=item['qty'])


def payment_success(request):
    for key in list(request.session.keys()):
        del request.session[key]
    return render(request, 'payment/payment-success.html')


def payment_fail(request):

    return render(request, 'payment/payment-fail.html')