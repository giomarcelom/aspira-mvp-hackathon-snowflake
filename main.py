# main.py
import snowflake.connector
from datetime import datetime
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

print(f"Starting Aspira MVP at {datetime.now()}")

# Snowflake connection with your credentials
conn = snowflake.connector.connect(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA")
)
print("Connected to Snowflake!")

# Visa input function
def get_visa_input():
    visa_data = {
        "current_visa": input("Enter current visa (e.g., H-1B): "),
        "expiration_date": input("Enter expiration date (YYYY-MM-DD): "),
        "pending_applications": input("Enter pending applications (comma-separated, e.g., EB-2): ").split(","),
        "expected_costs": float(input("Enter expected costs ($): "))
    }
    return visa_data

# Get and store visa data
visa_data = get_visa_input()
print("Visa data collected:", visa_data)

# Store in Snowflake
cur = conn.cursor()
cur.execute("INSERT INTO visa_data (visa_type, exp_date, apps, costs) VALUES (%s, %s, %s, %s)",
            (visa_data["current_visa"], visa_data["expiration_date"], str(visa_data["pending_applications"]), visa_data["expected_costs"]))
conn.commit()
print("Data stored in Snowflake!")
cur.close()
conn.close()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_price_from_gemini(ticker):
    prompt = f"What is the latest closing price for the stock ticker {ticker}? Provide just the price as a number, or 'Unable to retrieve' if not known."
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    try:
        price = float(response.text.strip())
        return price
    except ValueError:
        raise ValueError("Unable to retrieve price from Gemini.")

def get_ai_recommendation(visa_data):
    prompt = f"""
    Analyze this visa data for investment optimization:
    - Current Visa: {visa_data['current_visa']}
    - Expiration Date: {visa_data['expiration_date']}
    - Pending Applications: {visa_data['pending_applications']}
    - Expected Costs: ${visa_data['expected_costs']}
    - Current Date: {datetime.now().strftime('%Y-%m-%d')}
    Suggest an appropriate investment strategy (e.g., TIPS for short-term liquidity, SPY for long-term growth) and a specific ticker. Also suggest a risk multiplier (e.g., 1.5 for high uncertainty). Provide a concise recommendation, including the recommended ticker.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    return response.text

# Call AI recommendation
recommendation = get_ai_recommendation(visa_data)
print("AI Recommendation:", recommendation)

# Parse ticker from AI response (simple extraction, improve later)
ticker = "TIP"  # Default, parse from recommendation
if "SPY" in recommendation:
    ticker = "SPY"

# Fetch price using yfinance or Gemini fallback
try:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y")
    latest_price = hist["Close"].iloc[-1]
except Exception as e:
    print(f"yfinance failed: {str(e)}. Falling back to Gemini.")
    latest_price = get_price_from_gemini(ticker)

adjusted_target = visa_data["expected_costs"] * 1.5  # Use AI-suggested multiplier later
shares_needed = adjusted_target / latest_price
print(f"Recommended Investment: {ticker} (Latest Price: ${latest_price:.2f})")
print(f"Adjusted Target: ${adjusted_target:.2f}, Shares Needed: {shares_needed:.2f}")