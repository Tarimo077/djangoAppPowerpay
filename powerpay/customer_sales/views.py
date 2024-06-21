# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.paginator import Paginator
from .models import Customer, Sale
from .forms import CustomerForm, SaleForm
from datetime import timedelta

def customers_list(request):
    query = request.GET.get('q')
    if query:
        customers = Customer.objects.filter(name__icontains=query)
    else:
        customers = Customer.objects.all()
    paginator = Paginator(customers, 10)
    page = request.GET.get('page')
    customers = paginator.get_page(page)
    return render(request, 'customer_sales/customers_list.html', {'customers': customers, 'query': query})

def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    # Adjust the registration time by adding 3 hours
    registration_time = customer.date + timedelta(hours=3)
    return render(request, 'customer_sales/customer_detail.html', {'customer': customer, 'registration_time': registration_time})
    
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'customer_sales/customer_edit.html', {'form': form})

def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.delete()
        return redirect('customers_list')
    return render(request, 'customer_sales/customer_delete.html', {'customer': customer})

def add_customer(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customers_list')  # Adjust this redirect as necessary
    else:
        form = CustomerForm()
    return render(request, 'customer_sales/add_customer.html', {'form': form})

def sale_add(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.customer = customer
            sale.save()
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = SaleForm(current_customer_id=customer_id)
    return render(request, 'customer_sales/sale_add.html', {'form': form, 'customer': customer})
