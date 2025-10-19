from flask import Flask, render_template, request
import main
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    current_date = datetime.now().strftime("%Y-%m-%d")
    if request.method == 'POST':
        visa_data = {
            "current_visa": request.form['current_visa'],
            "expiration_date": request.form['expiration_date'],
            "pending_applications": request.form['pending_applications'].split(","),
            "expected_costs": float(request.form['expected_costs']),
            "investable_cash": float(request.form['investable_cash']),
            "monthly_contributions": float(request.form['monthly_contributions'])
        }
        gemini_portfolio, openai_portfolio, gemini_fv, openai_fv = main.recommend_investment(visa_data)
        gemini_justification = main.get_ai_recommendation(visa_data)
        openai_validation = main.validate_with_openai(
            [], [], 1.0,
            visa_data["expected_costs"],
            visa_data["investable_cash"],
            visa_data["monthly_contributions"],
            visa_data["expiration_date"]
        )
        openai_justification = f"Validation: {openai_validation['reason']}"
        return render_template('index.html', gemini_portfolio=gemini_portfolio, openai_portfolio=openai_portfolio, gemini_fv=gemini_fv, openai_fv=openai_fv, gemini_justification=gemini_justification, openai_justification=openai_justification, today=current_date)
    return render_template('index.html', today=current_date)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))