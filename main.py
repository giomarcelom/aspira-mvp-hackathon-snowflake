# main.py
import snowflake.connector
from datetime import datetime
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
from dateutil.relativedelta import relativedelta
from openai import OpenAI
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Update .env with:
# OPENAI_API_KEY=<your_openai_api_key>
# SNOWFLAKE_USER=giomartinez
# SNOWFLAKE_PASSWORD=T85sD5HkTKcG6St
# SNOWFLAKE_ACCOUNT=ujjdbqx-xib66121
# SNOWFLAKE_WAREHOUSE=COMPUTE_WH
# SNOWFLAKE_DATABASE=ASPIRA_DB
# SNOWFLAKE_SCHEMA=PUBLIC
# GEMINI_API_KEY=<your_gemini_key>
# AWS_EC2_METADATA_DISABLED=true

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

# Visa input function (to be called by app.py, not at startup)
def get_visa_input():
    return {
        "current_visa": input("Enter current visa (e.g., H-1B): "),
        "expiration_date": input("Enter expiration date (YYYY-MM-DD): "),
        "pending_applications": input("Enter pending applications (comma-separated, e.g., EB-2): ").split(","),
        "expected_costs": float(input("Enter expected visa costs ($): ")),
        "investable_cash": float(input("Enter current investable cash ($): ")),
        "monthly_contributions": float(input("Enter monthly investment contributions ($): "))
    }

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
        print(f"Gemini failed to retrieve price for {ticker}: {response.text.strip()}")
        return None

def get_ai_recommendation(visa_data):
    prompt = f"""
    You are an analyst for immigrants hedging visa uncertainties. Analyze this data to optimize investments:
    - Current Visa: {visa_data['current_visa']}
    - Expiration Date: {visa_data['expiration_date']}
    - Pending Applications: {visa_data['pending_applications']}
    - Expected Costs: ${visa_data['expected_costs']}
    - Investable Cash: ${visa_data['investable_cash']}
    - Monthly Contributions: ${visa_data['monthly_contributions']}
    - Current Date: {datetime.now().strftime('%Y-%m-%d')}
    Suggest a creative portfolio with allocation percentages, risk multiplier, and projected FV using FV = PV * (1+r)^n + PMT * [((1+r)^n - 1)/r]. Use current market data for expected returns. Structure output with sections: 'Visa & Financial Context Analysis', 'Creative Portfolio Strategy', 'Projected Growth with Compounding', 'Concise Recommendation'.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    return response.text

def get_historical_returns(tickers):
    if not tickers:
        return {}
    prompt = f"What are the 10-year average annual returns for the following tickers? Provide a list in the format 'TICKER: X.XX%': {', '.join(tickers)}. Use reliable historical data as of {datetime.now().strftime('%Y-%m-%d')}."
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    returns = {}
    for match in re.findall(r'(\w+):\s*([\d.]+)%', response.text):
        ticker, ret = match
        returns[ticker] = float(ret) / 100
    defaults = {"SPY": 0.10, "VTI": 0.1216, "VXUS": 0.045, "BND": 0.0075, "VNQ": 0.07, "AGG": 0.03, "VGSH": 0.009399999999999999, "ICLN": 0.05}
    for ticker in tickers:
        if ticker not in returns:
            returns[ticker] = defaults.get(ticker, 0.07)
    return returns

def validate_with_openai(tickers, allocations, risk_multiplier, expected_costs, investable_cash, monthly_contributions, expiration_date):
    try:
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=f"https://{os.getenv('SNOWFLAKE_ACCOUNT', 'ujjdbqx-xib66121')}.snowflakecomputing.com/api/v2/cortex/openai"
        )
        response = client.chat.completions.create(
            model="openai-gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a financial overseer reviewing an analyst's investment recommendation for an immigrant client."},
                {"role": "user", "content": f"The analyst suggested a portfolio with tickers {tickers}, allocations {allocations}, risk multiplier {risk_multiplier}, expected costs ${expected_costs}, investable cash ${investable_cash}, monthly contributions ${monthly_contributions}, and expiration date {expiration_date}. Validate this recommendation using the latest market data and research. Provide feedback in JSON format with fields: 'valid', 'reason', 'suggested_tickers', 'suggested_allocations', 'suggested_risk_multiplier'. If invalid, suggest improvements."}
            ]
        )
        result = response.choices[0].message.content
        logger.debug(f"Raw Open AI response (gpt-4.1): {result}")
        import json
        return json.loads(result)
    except Exception as e:
        logger.error(f"Open AI validation failed: {str(e)}")
        return {"valid": True, "reason": "Fallback to Gemini", "suggested_tickers": tickers, "suggested_allocations": allocations, "suggested_risk_multiplier": risk_multiplier}

def parse_recommendation(recommendation):
    # Improved parsing to handle varied formats
    ticker_matches = re.findall(r'(?:Asset Class|Investment Vehicles?):\s*(?:[^|]*\|)?\s*([A-Za-z0-9]+)\s*(?:[^|]*\|)?', recommendation, re.MULTILINE)
    if not ticker_matches:
        ticker_matches = re.findall(r'\b([A-Z]{2,4})\b', recommendation)  # Fallback to simple ticker regex
    tickers = list(dict.fromkeys(ticker_matches))  # Remove duplicates
    alloc_matches = re.findall(r'(?:Allocation|Allocation %):\s*(\d+\.?\d*%)', recommendation)
    allocations = [float(a.strip('%')) / 100 for a in alloc_matches] if alloc_matches else []
    multiplier_match = re.search(r"Risk Multiplier:\s*(\d+\.?\d*)", recommendation, re.IGNORECASE)
    multiplier = float(multiplier_match.group(1)) if multiplier_match else 1.0
    # Ensure allocations sum to 1 if tickers are found
    if tickers and allocations and sum(allocations) != 1.0:
        total = sum(allocations)
        allocations = [a / total for a in allocations]
    return tickers, multiplier, allocations

def recommend_investment(visa_data):
    conn = connect_to_snowflake()
    print(f"Starting Aspira MVP at {datetime.now()}")
    print("Connected to Snowflake!")
    store_in_snowflake(visa_data, conn)
    print("Visa data collected:", visa_data)
    print("Data stored in Snowflake!")
    conn.close()

    # Gemini Strategy
    gemini_recommendation = get_ai_recommendation(visa_data)
    print("Gemini Strategy Recommendation:", gemini_recommendation)
    gemini_tickers, gemini_risk_multiplier, gemini_allocations = parse_recommendation(gemini_recommendation)
    if not gemini_tickers or not gemini_allocations:
        gemini_tickers = ["SPY", "BND", "VNQ", "ICLN"]  # Default fallback tickers
        gemini_allocations = [0.4, 0.5, 0.1, 0.0]  # Adjusted to reflect structure
        gemini_risk_multiplier = 1.0

    # Open AI Strategy (if validation provides new suggestion)
    openai_validation = validate_with_openai(gemini_tickers, gemini_allocations, gemini_risk_multiplier, visa_data["expected_costs"], visa_data["investable_cash"], visa_data["monthly_contributions"], visa_data["expiration_date"])
    print("Open AI Validation:", openai_validation)
    openai_tickers = openai_validation["suggested_tickers"]
    openai_allocations = openai_validation["suggested_allocations"]
    openai_risk_multiplier = openai_validation["suggested_risk_multiplier"]
    if not openai_tickers or not openai_allocations:
        openai_tickers = gemini_tickers
        openai_allocations = gemini_allocations
        openai_risk_multiplier = gemini_risk_multiplier

    # Get 10-year historical returns for both strategies
    gemini_historical_returns = get_historical_returns(gemini_tickers)
    openai_historical_returns = get_historical_returns(openai_tickers)
    print("Gemini Historical 10-Year Returns (as decimals):", gemini_historical_returns)
    print("Open AI Historical 10-Year Returns (as decimals):", openai_historical_returns)

    # Weighted average expected return for both strategies
    gemini_weighted_r = sum(ret * alloc for ret, alloc in zip([gemini_historical_returns.get(t, 0.07) for t in gemini_tickers], gemini_allocations)) or 0.07
    openai_weighted_r = sum(ret * alloc for ret, alloc in zip([openai_historical_returns.get(t, 0.07) for t in openai_tickers], openai_allocations)) or 0.07
    print(f"Gemini Weighted Expected Annual Return: {gemini_weighted_r * 100:.2f}%")
    print(f"Open AI Weighted Expected Annual Return: {openai_weighted_r * 100:.2f}%")

    # Fetch prices and calculate for both strategies
    def calculate_portfolio(tickers, allocations, risk_multiplier, expected_costs):
        portfolio = []
        cost_adjusted_target = expected_costs * risk_multiplier
        total_investable = visa_data["investable_cash"] + (visa_data["monthly_contributions"] * (months := (datetime.strptime(visa_data["expiration_date"], "%Y-%m-%d") - datetime.now()).days / 30))
        surplus_investable = total_investable - cost_adjusted_target
        total_allocation = sum(allocations)
        for ticker, allocation in zip(tickers, allocations):
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1y")
                if not hist.empty:
                    latest_price = hist["Close"].iloc[-1]
                else:
                    raise ValueError("No data available")
            except Exception as e:
                print(f"yfinance failed for {ticker}: {str(e)}. Falling back to finance card or default.")
                latest_price = {"SPY": 580.0, "VTI": 327.3, "VXUS": 74.2, "BND": 74.88, "VNQ": 91.17, "AGG": 100.0, "VGSH": 58.92, "ICLN": 16.53}.get(ticker, get_price_from_gemini(ticker))
                if latest_price is None:
                    print(f"No price data for {ticker}, using default: $100.00")
                    latest_price = 100.0

            adjusted_target = cost_adjusted_target * (allocation / total_allocation)
            shares_needed = adjusted_target / latest_price if latest_price else 0
            portfolio.append((ticker, latest_price, adjusted_target, shares_needed))
            print(f"Recommended Investment ({'Gemini Strategy' if tickers == gemini_tickers else 'Open AI Strategy'}): {ticker} (Latest Price: ${latest_price:.2f})")
            print(f"Adjusted Target ({'Gemini Strategy' if tickers == gemini_tickers else 'Open AI Strategy'}): ${adjusted_target:.2f}, Shares Needed: {shares_needed:.2f}")
        return portfolio

    gemini_portfolio = calculate_portfolio(gemini_tickers, gemini_allocations, gemini_risk_multiplier, visa_data["expected_costs"])
    openai_portfolio = calculate_portfolio(openai_tickers, openai_allocations, openai_risk_multiplier, visa_data["expected_costs"])

    # Compounding projection for both strategies based on expiration date
    exp_date = datetime.strptime(visa_data["expiration_date"], "%Y-%m-%d")
    today = datetime.now()
    months = (exp_date - today).days / 30
    gemini_r = gemini_weighted_r / 12
    openai_r = openai_weighted_r / 12
    gemini_fv = visa_data["investable_cash"] * (1 + gemini_r)**months + visa_data["monthly_contributions"] * (((1 + gemini_r)**months - 1) / gemini_r) if gemini_r else 0
    openai_fv = visa_data["investable_cash"] * (1 + openai_r)**months + visa_data["monthly_contributions"] * (((1 + openai_r)**months - 1) / openai_r) if openai_r else 0
    print(f"Gemini Projected Portfolio Value in {months:.1f} months: ${gemini_fv:.2f}")
    print(f"Open AI Projected Portfolio Value in {months:.1f} months: ${openai_fv:.2f}")

    return gemini_portfolio, openai_portfolio, gemini_fv, openai_fv

# No direct call to get_visa_input() here; handled by app.py