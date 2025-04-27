from flask import Flask, render_template, request, session
import requests
import re
import pandas as pd
import random

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Required for session support


def extract_first_answer(text):
    text = text.strip()
    # Clean the response from the bot
    text = re.sub(r'\b(Bot|Assistant)\s*:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(OUTPUT|Answer)\s*:\s*', '', text, flags=re.IGNORECASE)

    for tag in ['RESULT', 'INST', 'ANS']:
        match = re.search(rf'\[{tag}\](.*?)\[/\s*{tag}\]', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    text = re.sub(r'#?\*\[.*?\]', '', text)
    sentence = re.split(r'[.!?]', text)[0]
    return sentence.strip()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return "This is a simple Flask app."


@app.route('/debug')
def debug():
    return "This is the debug route."


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'history' not in session:
        session['history'] = []

    if request.method == 'POST':
        user_message = request.form['message']

        # Extract the city from the user message
        city = extract_city(user_message)  # Helper function to extract city name

        if city:
            # Step 1: Get the temperature for the city from the weather API
            city_temperature = get_city_temperature(city)

            # Step 2: Use the CSV to find a country with opposite temperature
            opposite_city = find_opposite_temperature_city(city_temperature)

            bot_reply = f"The average temperature in {city} is {city_temperature}°C. A great place to visit would be {opposite_city} for a completely different climate!"
        else:
            bot_reply = "Sorry, I couldn't identify your city. Could you please provide a city name?"

        # Append to chat history
        session['history'].append({'user': user_message, 'bot': bot_reply})
        session.modified = True

    return render_template('chat.html', history=session.get('history', []))


# Extract city from message using CSV file for reference
def extract_city(message):
    df = load_and_transform_csv()

    if 'City' not in df.columns:
        raise ValueError("CSV does not have a 'City' column")

    cities_list = df['City'].dropna().unique()

    message_lower = message.lower()

    for city in cities_list:
        if isinstance(city, str) and city.lower() in message_lower:
            return city

    return None


# Get city temperature from Visual Crossing API
def get_city_temperature(city):
    api_key = ''  # Replace with your actual API key
    url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city}?key={api_key}'

    try:
        response = requests.get(url)
        data = response.json()
        return data['days'][0]['temp']
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None


# Load CSV data, take average for a city, and convert to Fahrenheit
def load_and_transform_csv():
    # Extract
    df = pd.read_csv('world_temps.csv')

    # Transform
    # Select only the month columns and convert them to numeric
    month_columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for month in month_columns:
        df[month] = pd.to_numeric(df[month], errors='coerce')  # make sure they're numbers

    # Calculate average temperature in Celsius
    df['AvgTemperatureC'] = df[month_columns].mean(axis=1)

    # Convert Celsius to Fahrenheit
    df['AvgTemperatureF'] = df['AvgTemperatureC'] * 9 / 5 + 32

    # Keep only necessary columns
    result = df[['Country', 'City', 'AvgTemperatureF']]

    # Clean city names (optional but good)
    result['City'] = result['City'].str.strip().str.title()

    return result


# Find a city with an opposite temperature based on conditions
def find_opposite_temperature_city(city_temperature):
    df = load_and_transform_csv()

    if city_temperature >= 60:
        # Find cities with average temperature < 40°C
        opposite_city_df = df[df['AvgTemperatureF'] < 40]
    else:
        # Find cities with average temperature > 60°C
        opposite_city_df = df[df['AvgTemperatureF'] > 60]

    # Ensure we have at least one opposite city to choose from
    if not opposite_city_df.empty:
        opposite_city = opposite_city_df.sample(n=1)
        country = opposite_city['Country'].values[0]
        city = opposite_city['City'].values[0]
        temp = opposite_city['AvgTemperatureF'].values[0]
        return f"{city},{country} (Avg Temp: {temp:.1f}°F)"

    return "Sorry, no suitable opposite temperature city found."


@app.route('/clear')
def clear():
    session.pop('history', None)
    return render_template('chat.html', history=[])


if __name__ == '__main__':
    app.run(debug=True)
