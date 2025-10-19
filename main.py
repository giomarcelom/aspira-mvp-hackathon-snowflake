# main.py
import snowflake.connector
from datetime import datetime
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
import math  # For compounding calculations

# Load environment variables
load_dotenv()

# Snowflake connection with your credentials
def connect_to_snowflake():
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA")
    )

# Visa input function (expanded for investment details)
def get_visa_input():
    visa_data = {
        "current_visa": input("Enter current visa (e.g., H-1B): "),
        "expiration_date": input("Enter expiration date (YYYY-MM-DD): "),
        "pending_applications": input("Enter pending applications (comma-separated, e.g., EB-2): ").split(","),
        "expected_costs": float(input("Enter expected visa costs ($): ")),
        "investable_cash": float(input("Enter current investable cash ($): ")),
        "monthly_contributions": float(input("Enter monthly investment contributions ($): "))
    }
    return visa_data

# Store in Snowflake
def store_in_snowflake(visa_data, conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO visa_data (visa_type, exp_date, apps, costs, investable_cash, monthly_contributions) VALUES (%s, %s, %s, %s, %s, %s)",
                (visa_data["current_visa"], visa_data["expiration_date"], str(visa_data["pending_applications"]), visa_data["expected_costs"], visa_data["investable_cash"], visa_data["monthly_contributions"]))
    conn.commit()
    cur.close()

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
    Analyze this visa data for investment optimization, maximizing returns while hedging visa uncertainties:
    - Current Visa: {visa_data['current_visa']}
    - Expiration Date: {visa_data['expiration_date']}
    - Pending Applications: {visa_data['pending_applications']}
    - Expected Costs: ${visa_data['expected_costs']}
    - Investable Cash: ${visa_data['investable_cash']}
    - Monthly Contributions: ${visa_data['monthly_contributions']}
    - Current Date: {datetime.now().strftime('%Y-%m-%d')}
    Suggest a creative portfolio strategy (e.g., mix of ETFs, bonds, stocks, alternatives) with expected returns, based on current market dynamics. Include 3-5 diverse tickers, allocation percentages, risk multiplier, and projected growth with compounding (FV = PV * (1+r)^n + PMT * [((1+r)^n - 1)/r]). Provide a concise recommendation.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    return response.text

def parse_recommendation(recommendation):
    # Simple parsing for tickers, multiplier, allocations (improve with regex as needed)
    ticker_match = re.search(r"Recommended tickers:\s*(.+)", recommendation, re.IGNORECASE)
    multiplier_match = re.search(r"Risk Multiplier:\s*(\d+\.?\d*)", recommendation, re.IGNORECASE)
    tickers = ticker_match.group(1).split(",") if ticker_match else ["TIP"]
    multiplier = float(multiplier_match.group(1)) if multiplier_match else 1.5
    # Assume equal allocations for now (refine later)
    allocations = [1.0 / len(tickers) for _ in tickers]
    return tickers, multiplier, allocations

def recommend_investment(visa_data):
    conn = connect_to_snowflake()
    print(f"Starting Aspira MVP at {datetime.now()}")
    print("Connected to Snowflake!")
    store_in_snowflake(visa_data, conn)
    print("Visa data collected:", visa_data)
    print("Data stored in Snowflake!")
    conn.close()

    recommendation = get_ai_recommendation(visa_data)
    print("AI Recommendation:", recommendation)
    tickers, risk_multiplier, allocations = parse_recommendation(recommendation)

    # Fetch prices and calculate
    portfolio = []
    for ticker, allocation in zip(tickers, allocations):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            latest_price = hist["Close"].iloc[-1]
        except Exception as e:
            print(f"yfinance failed for {ticker}: {str(e)}. Falling back to Gemini.")
            latest_price = get_price_from_gemini(ticker)

        adjusted_target = visa_data["expected_costs"] * risk_multiplier * allocation
        shares_needed = adjusted_target / latest_price
        portfolio.append((ticker, latest_price, adjusted_target, shares_needed))
        print(f"Recommended Investment: {ticker} (Latest Price: ${latest_price:.2f})")
        print(f"Adjusted Target: ${adjusted_target:.2f}, Shares Needed: {shares_needed:.2f}")

    # Compounding projection (assume 5% annual return, monthly compounding)
    months = 12  # Default, calculate based on expiration later
    r = 0.05 / 12  # Monthly rate
    fv = visa_data["investable_cash"] * (1 + r)**months + visa_data["monthly_contributions"] * (((1 + r)**months - 1) / r)
    print(f"Projected Portfolio Value in {months} months: ${fv:.2f}")

    return portfolio, fv

# Get visa data
visa_data = get_visa_input()

# Call recommend_investment
portfolio, fv = recommend_investment(visa_data)