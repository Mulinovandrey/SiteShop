from django.urls import path
from .views import *



app_name = 'payment'

urlpatterns = [
    path('shipping/', shipping, name='shipping'),
    path('checkout/', checkout, name='checkout'),
    path('complete-order/', complete_order, name='complete-order'),
    path('payment-success/', payment_success, name='payment-success'),
    path('payment-fail/', payment_fail, name='payment-fail'),

]