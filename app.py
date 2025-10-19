from flask import Flask, render_template, request
import main
import os

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
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
        # Capture Gemini justification (assuming it's the recommendation text)
        gemini_justification = main.get_ai_recommendation(visa_data)  # This returns the full recommendation text
        # Capture Open AI justification (assuming it's from validation)
        openai_validation = main.validate_with_openai(*[visa_data.get(k, []) for k in ['expected_costs', 'investable_cash', 'monthly_contributions', 'expiration_date']])
        openai_justification = f"Validation: {openai_validation['reason']}"  # Use reason as justification
        return render_template('index.html', gemini_portfolio=gemini_portfolio, openai_portfolio=openai_portfolio, gemini_fv=gemini_fv, openai_fv=openai_fv, gemini_justification=gemini_justification, openai_justification=openai_justification)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))