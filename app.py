import os
import re
import sqlite3
from flask import Flask, request, jsonify, render_template

# --- Flask Application ---
app = Flask(__name__, static_folder='static', template_folder='templates')

# Use environment variable for database path or default to local
DATABASE = os.environ.get('DATABASE_URL', 'orders.db')

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        db.close()

# Initialize the database when the app starts
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_orders', methods=['POST'])
def save_orders():
    try:
        data = request.get_json()
        team = data.get('team')
        orders_text = data.get('orders')

        if not team or not orders_text:
            return jsonify({'success': False, 'message': 'Missing team or orders data.'}), 400

        parsed_orders = parse_orders(orders_text)
        saved_count = 0

        db = get_db()
        cursor = db.cursor()

        for order in parsed_orders:
            try:
                cursor.execute(
                    'INSERT INTO orders (team, customer_name, price) VALUES (?, ?, ?)',
                    (team, order['customer_name'], order['price'])
                )
                saved_count += 1
            except Exception as e:
                print(f"Error saving order: {e}")
                db.rollback()
                return jsonify({'success': False, 'message': f'Error saving order: {e}'}), 500

        db.commit()
        db.close()

        return jsonify({'success': True, 'message': f'تم حفظ {saved_count} أوردرات بنجاح!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

def parse_orders(orders_text):
    parsed_data = []
    # Split by lines, then by common separators like 'ج', 'جنيه', or newlines
    # Regex to capture name and amount, handling various formats and separators
    # This regex is more robust to handle different line endings and variations
    order_lines = re.split(r'\n|\r\n', orders_text)
    
    for line in order_lines:
        line = line.strip()
        if not line:
            continue

        # Regex to find name and amount. Handles 'ج', 'جنيه', '+', and optional spaces.
        # It also tries to capture the name before the amount.
        match = re.search(r'(.+?)\s*[-—]?\s*(\d+\.?\d*)\s*(?:ج|جنيه|\+)?', line)
        if match:
            customer_name = match.group(1).strip()
            price = float(match.group(2))
            parsed_data.append({'customer_name': customer_name, 'price': price})
        else:
            print(f"Could not parse line: {line}")

    return parsed_data

@app.route('/get_report', methods=['GET'])
def get_report():
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute('SELECT team, COUNT(*) as order_count, SUM(price) as total_sales FROM orders GROUP BY team')
        report_data = cursor.fetchall()
        db.close()

        report_summary = {}
        total_orders = 0
        total_sales = 0.0

        for row in report_data:
            team = row['team']
            order_count = row['order_count']
            total_sales_team = row['total_sales'] if row['total_sales'] is not None else 0.0

            report_summary[team] = {
                'order_count': order_count,
                'total_sales': total_sales_team
            }
            total_orders += order_count
            total_sales += total_sales_team

        return jsonify({
            'success': True,
            'report_summary': report_summary,
            'total_orders': total_orders,
            'total_sales': total_sales
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

