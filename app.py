from flask import Flask, render_template, request
import main

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
        return render_template('index.html', gemini_portfolio=gemini_portfolio, openai_portfolio=openai_portfolio, gemini_fv=gemini_fv, openai_fv=openai_fv)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))