from flask import Flask, request, render_template_string
import main

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        visa_data = {
            "current_visa": request.form['current_visa'],
            "expiration_date": request.form['expiration_date'],
            "pending_applications": request.form['pending_applications'].split(","),
            "expected_costs": float(request.form['expected_costs'])
        }
        # Call main functions
        recommendation = main.get_ai_recommendation(visa_data)
        # Note: recommend_investment prints to console; we'll capture it later
        main.recommend_investment(visa_data)
        return render_template_string("""
            <h1>Aspira MVP</h1>
            <p>Visa Data: {{ visa_data }}</p>
            <p>AI Recommendation: {{ recommendation }}</p>
            <p>Check console for Investment Recommendation</p>
            <a href="/">Back</a>
            """, visa_data=visa_data, recommendation=recommendation)
    return render_template_string("""
        <h1>Aspira MVP</h1>
        <form method="post">
            <label>Current Visa: <input type="text" name="current_visa" required></label><br>
            <label>Expiration Date (YYYY-MM-DD): <input type="text" name="expiration_date" required></label><br>
            <label>Pending Applications (comma-separated): <input type="text" name="pending_applications" required></label><br>
            <label>Expected Costs ($): <input type="number" name="expected_costs" step="0.01" required></label><br>
            <button type="submit">Submit</button>
        </form>
        """)

if __name__ == '__main__':
    # Open browser automatically
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=True)