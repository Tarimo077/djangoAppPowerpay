from django.shortcuts import render, redirect
import requests
from requests.auth import HTTPBasicAuth
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import plotly.io as pio
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Constants
BASE_URL = "https://appliapay.com/"
AUTH = HTTPBasicAuth('admin', '123Give!@#')

def fetch_data(endpoint):
    response = requests.get(BASE_URL + endpoint, auth=AUTH)
    response.raise_for_status()
    return response.json()


def login_page(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home_page')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

def logout_page(request):
    logout(request)
    return redirect('login')

@login_required
def homepage(request):
    data = fetch_data("allDeviceDataDjango")
    runtime = data['runtime']
    data = data['rawData']
    data = pd.DataFrame(data)
    data_list = data.to_dict(orient='records')
    meals, mls = classify_and_count_meals(data_list)
    morning, afternoon, night = categorize_kwh(data_list)
    meal_counts = [info['count'] for device_id, info in meals.items()]
    sumKwh = 0
    sumRuntime = 0
    sumMeals = 0
    for z in meal_counts:
        sumMeals = sumMeals + z    
    for x in data_list:
        sumKwh = sumKwh + x['kwh']
    for y in runtime.values():
        sumRuntime = sumRuntime + y
    charts = generate_charts(data, runtime, meals, morning, afternoon, night)

    context = {
        'line_chart': charts['line_chart'],
        'pie_chart': charts['pie_chart'],
        'meals_pie_html': charts['meals_pie_html'],
        'meals_kwh_html': charts['meals_kwh_html'],
        'cooking_time_pie_html': charts['cooking_time_pie_html'],
        'meals_emissions_html': charts['meals_emissions_html'],
        'pie_chart_emissions': charts['pie_chart_emissions'],
        'sumKwh': sumKwh,
        'sumRuntime': sumRuntime,
        'sumEmissions': sumKwh*0.28*0.4999,
        'sumEnergyCost': sumKwh*23.0,
        'sumMeals': sumMeals
    }
    return render(request, 'index.html', context)

@login_required
def devices_page(request):
    data = fetch_data("command")
    data = pd.DataFrame(data)
    if not data.empty:
        # Sorting and handling different naming conventions
        def sort_key(x):
            if x == 'OfficeFridge1':
                return float('inf')
            elif x.startswith('device'):
                return int(x.split('device')[-1])
            elif x.startswith('JD-'):
                try:
                    return int(x.split('-')[-1].split('device')[-1])
                except ValueError:
                    return float('inf') - 1
            else:
                return float('inf') - 1
        
        data['sort_key'] = data['deviceID'].apply(sort_key)
        data = data.sort_values(by='sort_key')

        # Convert 'time' to datetime format
        data['time'] = pd.to_datetime(data['time'], format="%Y-%m-%dT%H:%M:%S.%fZ")

        # Handle search query
        query = request.GET.get('q')
        if query:
            data = data[data['deviceID'].str.lower().str.contains(query.lower())]

        # Convert the DataFrame to a list of dictionaries
        devices_list = data.to_dict(orient='records')

        # Implement pagination with 10 items per page
        paginator = Paginator(devices_list, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
    else:
        page_obj = []

    device_list = [device['deviceID'] for device in devices_list]

    context = {
        'devices_table': page_obj,
        'query': query,
        'device_list': device_list  # Add the device list to the context
    }

    return render(request, 'devices.html', context)


def classify_and_count_meals(data):
    sorted_data = sorted(data, key=lambda x: (x['deviceID'], x['txtime']))
    device_meal_counts = {}
    day_meal_counts = {}

    for entry in sorted_data:
        if entry['deviceID'] != 'OfficeFridge1':
            device_id = entry['deviceID']
            txtime = datetime.strptime(str(entry['txtime']), "%Y%m%d%H%M%S")

            if device_id not in device_meal_counts:
                device_meal_counts[device_id] = {'count': 0, 'last_txtime': None}
            if device_meal_counts[device_id]['last_txtime'] is not None:
                time_diff = txtime - device_meal_counts[device_id]['last_txtime']
                if time_diff > timedelta(minutes=20):
                    device_meal_counts[device_id]['count'] += 1
            else:
                device_meal_counts[device_id]['count'] += 1

            date = txtime.strftime('%Y-%m-%d')
            if date not in day_meal_counts:
                day_meal_counts[date] = {}
            if device_id not in day_meal_counts[date]:
                day_meal_counts[date][device_id] = 0
            if 'last_txtime' in day_meal_counts[date]:
                time_diff = txtime - day_meal_counts[date]['last_txtime']
                if time_diff > timedelta(minutes=20):
                    day_meal_counts[date][device_id] += 1
            else:
                day_meal_counts[date][device_id] += 1
            
            device_meal_counts[device_id]['last_txtime'] = txtime
            day_meal_counts[date]['last_txtime'] = txtime

    total_meals_per_day = {date: sum(count for device, count in counts.items() if device != 'last_txtime') for date, counts in day_meal_counts.items()}
    return device_meal_counts, total_meals_per_day

def categorize_kwh(data):
    morning_kwh = 0
    afternoon_kwh = 0
    night_kwh = 0
    for record in data:
        hour = int(str(record['txtime'])[8:10])
        if 4 <= hour < 11:
            morning_kwh += record['kwh']
        elif 11 <= hour < 17:
            afternoon_kwh += record['kwh']
        else:
            night_kwh += record['kwh']
    return morning_kwh, afternoon_kwh, night_kwh

def generate_charts(data, runtime, meals, morning, afternoon, night):
    # Convert data to DataFrame
    df = pd.DataFrame(data)
    df['txtime'] = pd.to_datetime(df['txtime'], format='%Y%m%d%H%M%S')
    df = df[df['kwh'] >= 0]

    device_ids = [device_id for device_id, info in meals.items()]
    meal_counts = [info['count'] for device_id, info in meals.items()]
    runtime_device_ids = list(runtime.keys())
    runtime_hours = list(runtime.values())

    # Create Pie Charts
    cooking_time_pie = create_pie_chart(runtime_device_ids, runtime_hours, 'Cooking Time by Device')
    meals_pie = create_pie_chart(device_ids, meal_counts, 'Meals Distribution by Device')
    kwh_pie = create_pie_chart(["Breakfast", "Lunch", "Supper"], [morning, afternoon, night], 'KWH Per Meal')
    emissions_pie = create_pie_chart(["Breakfast", "Lunch", "Supper"], [morning * 0.4999 * 0.28, afternoon * 0.4999 * 0.28, night * 0.4999 * 0.28], 'Emissions Per Meal')

    # Line Chart
    energy_line_chart = create_line_chart(df, 'txtime', 'kwh', 'Energy Consumption')

    # Device kWh Pie Chart
    df_pie = df.groupby('deviceID')['kwh'].sum().reset_index()
    kwh_pie_chart = create_pie_chart(df_pie['deviceID'], df_pie['kwh'], 'kWh Distribution by Device')

    # Emissions per Device Pie Chart
    df_pie_emissions = df.copy()
    df_pie_emissions['emissions'] = df_pie_emissions['kwh'] * 0.4999 * 0.28
    emissions_device_pie_chart = create_pie_chart(df_pie_emissions['deviceID'], df_pie_emissions['emissions'], 'Carbon Emissions Per Device')

    return {
        'line_chart': pio.to_html(energy_line_chart, full_html=False),
        'pie_chart': pio.to_html(kwh_pie_chart, full_html=False),
        'meals_pie_html': pio.to_html(meals_pie, full_html=False),
        'meals_kwh_html': pio.to_html(kwh_pie, full_html=False),
        'cooking_time_pie_html': pio.to_html(cooking_time_pie, full_html=False),
        'meals_emissions_html': pio.to_html(emissions_pie, full_html=False),
        'pie_chart_emissions': pio.to_html(emissions_device_pie_chart, full_html=False)
    }

def create_pie_chart(names, values, title):
    pie_chart = px.pie(names=names, values=values, title=title)
    pie_chart.update_traces(textposition='inside', hoverinfo='label+value+percent',
                            hovertemplate='<b>%{label}: %{value}</b>')
    pie_chart.update_layout(
        showlegend=True,
        autosize=True,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        title_x=0.5
    )
    return pie_chart

def create_line_chart(df, x_column, y_column, title):
    line_chart = px.line(df, x=x_column, y=y_column, title=title, labels={x_column: 'Time', y_column: 'kWh'})
    line_chart.update_traces(line=dict(color="#0ead00"), hovertemplate='%{x}<br>%{y} kWh<br>Device ID: %{text}')
    line_chart.update_traces(text=df['deviceID'])
    line_chart.update_layout(
        xaxis_title='Time',
        yaxis_title='kWh',
        showlegend=False,
        autosize=True,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        title_x=0.5
    )
    return line_chart

@login_required
def transactions_page(request):
    data = fetch_data("mpesarecords")
    data = pd.DataFrame(data)
    # Convert 'transtime' to datetime format
    data['transtime'] = pd.to_datetime(data['transtime'], format='%Y%m%d%H%M%S')

    # Sort the data by 'transtime' in descending order
    data = data.sort_values(by='transtime', ascending=False)

    # Handle search query
    query = request.GET.get('q')
    if query:
        data = data[data.apply(lambda row: query.lower() in row['name'].lower() or
                                            query.lower() in row['ref'].lower() or
                                            query.lower() in row['id'].lower(), axis=1)]

    # Convert the DataFrame to a list of dictionaries
    transactions_list = data.to_dict(orient='records')

    # Implement pagination with 10 items per page
    paginator = Paginator(transactions_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Line chart data
    line_chart_data = data[['transtime', 'amount']].sort_values(by='transtime')

    # Plotting the line chart
    fig_line = px.line(line_chart_data, x='transtime', y='amount', title='Amount Over Time', labels={'transtime': 'Transaction Time', 'amount': 'Amount'})
    fig_line.update_traces(line=dict(color="#0ead00"), hovertemplate='%{x}<br>Amount: %{y}')
    fig_line.update_traces(text=data['id'])  # Pass the transaction ID as text for hover template
    fig_line.update_layout(
        xaxis_title='Transaction Time',
        yaxis_title='Amount',
        showlegend=False,
        autosize=True,
        title_x = 0.5,
        height=400,
        #width=0.7 * 800,  # Assuming an 800px base width
        margin=dict(l=20, r=20, t=40, b=20)
    )
    line_chart = pio.to_html(fig_line, full_html=False)

    context = {
        'transactions_table': page_obj,  # Pass the page object to the template
        'query': query,  # Pass the query to the template to preserve it in the search box
        'line_chart': line_chart,  # Pass the line chart HTML to the template
    }

    return render(request, 'transactions.html', context)

def fetch_data_with_params(endpoint, dev, range_value):
    response = requests.get(BASE_URL + endpoint +"?device="+dev+"&range=" + str(range_value), auth=AUTH)
    response.raise_for_status()
    return response.json()

@login_required
def device_data_page(request, device_id):
    range_value = request.GET.get('range', 9999999)
    
    # Fetch data based on device_id and range_value
    data = fetch_data_with_params("deviceDataDjangoo", device_id, range_value)
    runtime = data['runtime']
    sum_kwh = data['sumKwh']
    emissions = sum_kwh * 0.4999 * 0.28
    energy_cost = sum_kwh * 23.0
    meals_with_durations = data['mealsWithDurations'][::-1]
    total_meals_per_day = data['totalMealsPerDay']
    
    df = pd.DataFrame(list(total_meals_per_day.items()), columns=["Date", "Meals"])
    fig_line = px.line(df, x="Date", y="Meals", title="Total Meals Per Day", labels={"Meals": "Number of Meals"})
    fig_line.update_traces(line=dict(color="#0ead00"), hovertemplate='%Date: %{x}<br>Number of Meals: %{y}')
    fig_line.update_layout(
        xaxis_title='Date',
        yaxis_title='Meals',
        showlegend=False,
        autosize=True,
        title_x=0.5,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    meals_per_day_chart = pio.to_html(fig_line, full_html=False)

    dat = fetch_data("command")
    for z in dat:
        if z["deviceID"] == device_id:
            status = z["active"]
    dat = pd.DataFrame(dat)
    if not dat.empty:
        # Sorting and handling different naming conventions
        def sort_key(x):
            if x == 'OfficeFridge1':
                return float('inf')
            elif x.startswith('device'):
                return int(x.split('device')[-1])
            elif x.startswith('JD-'):
                try:
                    return int(x.split('-')[-1].split('device')[-1])
                except ValueError:
                    return float('inf') - 1
            else:
                return float('inf') - 1
        
        dat['sort_key'] = dat['deviceID'].apply(sort_key)
        dat = dat.sort_values(by='sort_key')

    for x in meals_with_durations:
        x['mealDuration'] = x['mealDuration'] / 60
        x['startTime'] = datetime.strptime(x['startTime'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d %b %Y %I:%M:%S %p')
        x['endTime'] = datetime.strptime(x['endTime'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d %b %Y %I:%M:%S %p')
        x['emissions'] = x['totalKwh']*0.4999*0.28
        x['energy_cost'] = x['totalKwh']*23.0

    # Pagination logic
    paginator = Paginator(meals_with_durations, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    dev_List = dat['deviceID'].tolist()

    context = {
        "device_id": str(device_id),  # Ensure device_id is a string
        "runtime": runtime,
        "sum_kwh": sum_kwh,
        "emissions": emissions,
        "meals_with_durations": page_obj,  # Pass paginated meals_with_durations
        "total_meals_per_day": total_meals_per_day,
        "meals_per_day_chart": meals_per_day_chart,
        "energy_cost": energy_cost,
        "dev_List": dev_List,  # Ensure dev_List is a list of strings
        "status": status,
        "selected_range": str(range_value)
    }

    return render(request, "device_data.html", context)