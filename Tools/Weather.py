import requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers",
    95: "a thunderstorm", 96: "a thunderstorm with hail", 99: "a thunderstorm with hail",
}


def get_weather(city: str) -> str:
    if not city or not city.strip():
        return "Sorry boss, which city's weather do you want?"
    try:
        geo = requests.get(GEO_URL, params={"name": city, "count": 1}, timeout=5).json()
        places = geo.get("results")
        if not places:
            return f"Sorry boss, I couldn't find a city called {city}."
        place = places[0]

        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
        }
        data = requests.get(FORECAST_URL, params=params, timeout=5).json()
        cur = data["current"]
        sky = WEATHER_CODES.get(cur["weather_code"], "unclear conditions")
        return (
            f"In {place['name']} it is {cur['temperature_2m']:.0f} degrees Celsius "
            f"with {sky}. It feels like {cur['apparent_temperature']:.0f}, "
            f"humidity is {cur['relative_humidity_2m']} percent, "
            f"and wind is {cur['wind_speed_10m']:.0f} kilometres per hour."
        )
    except Exception as e:
        print(f"[Weather] {e}")
        return "Sorry boss, something went wrong while fetching the weather."
