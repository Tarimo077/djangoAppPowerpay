from django.urls import path
from . import views

urlpatterns = [
    path('', views.customers_list, name='customers_list'),
    path('customer/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customer/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customer/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    path('customer/<int:customer_id>/sale/add/', views.sale_add, name='sale_add'),
    path('add_customer/', views.add_customer, name='add_customer'),
]
