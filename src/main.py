import os
import sys
from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
import pytz
import sqlite3
import re

# DON\'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.user import db
from src.routes.user import user_bp
from src.routes.order import order_bp, parse_order_text_with_chatgpt, parse_order_text_fallback

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(order_bp, url_prefix='/api')

# Database setup
def get_db_path():
    return os.path.join(basedir, 'orders.db')

def init_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team TEXT NOT NULL,
            order_count INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()

def get_db_connection():
    init_db()
    return sqlite3.connect(get_db_path())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save_orders', methods=['POST'])
def save_orders():
    try:
        data = request.get_json()
        team = data.get('team', '')
        orders_text = data.get('orders', '')
        
        if not team or not orders_text.strip():
            return jsonify({'error': 'الرجاء اختيار الفريق وإدخال نصوص الأوردرات.'}), 400

        # Use the parsing logic from order.py
        total_amount, order_count = parse_order_text_with_chatgpt(orders_text)
        if order_count == 0:
            total_amount, order_count = parse_order_text_fallback(orders_text)

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if order_count > 0:
            cursor.execute('INSERT INTO orders (team, order_count) VALUES (?, ?)', (team, order_count))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'تم حفظ {order_count} أوردرات بنجاح!', 'orders_saved': order_count}), 200
    except Exception as e:
        return jsonify({'error': f'حدث خطأ: {str(e)}'}), 500

@app.route('/api/clear_data', methods=['POST'])
def clear_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM orders')
        conn.commit()
        conn.close()
        return jsonify({'message': 'تم مسح جميع البيانات بنجاح!'}), 200
    except Exception as e:
        return jsonify({'error': f'حدث خطأ أثناء مسح البيانات: {str(e)}'}), 500

def get_facebook_ads_data_simplified():
    return {
        "A": {"spend": 500, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "B": {"spend": 600, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "C": {"spend": 700, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "C1": {"spend": 800, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "Follow-up": {"spend": 400, "orders": 0, "held": 0, "sales": 0, "roas": 0}
    }

@app.route('/api/generate_report', methods=['GET'])
def generate_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT team, SUM(order_count) FROM orders GROUP BY team ORDER BY team')
        orders_by_team = dict(cursor.fetchall())
        
        conn.close()

        facebook_data = get_facebook_ads_data_simplified()
        
        for team in facebook_data:
            facebook_data[team]["orders"] = orders_by_team.get(team, 0)

        for team_name, data in facebook_data.items():
            if team_name != 'Follow-up':
                data['sales'] = data['orders'] * 100
                data['held'] = data['spend'] / data['orders'] if data['orders'] > 0 else 0
                data['roas'] = data['sales'] / data['spend'] if data['spend'] > 0 else 0
            else:
                data['sales'] = data['orders'] * 80

        report_text = format_detailed_report(facebook_data)
        
        return jsonify({
            "success": True,
            "report": report_text,
            "api_error": None
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": f"حدث خطأ: {str(e)}"}), 500

def format_detailed_report(data):
    cairo_tz = pytz.timezone('Africa/Cairo')
    now = datetime.now(cairo_tz)
    
    report = f"تاريخ التقرير: {now.strftime("%Y-%m-%d")}\n"
    report += f"الوقت: {now.strftime("%I:%M %p")}\n"
    report += "===================\n\n"
    
    teams = ['A', 'B', 'C', 'C1', 'Follow-up']
    
    for team in teams:
        team_data = data[team]
        
        if team == 'A':
            report += f"تيم (A)\n"
        elif team == 'Follow-up':
            report += f"تيم (فولو أب)\n"
        else:
            report += f"تيم ({team})\n"
        
        if team != 'Follow-up':
            report += f"الصرف :/ {team_data['spend']:,} ج\n"
            report += f"عدد الاوردرات / {team_data['orders']}\n"
            report += f"التكلفة : / {team_data['held']:.2f} ج\n"
            report += f"المبيعات (غير شاملة الشحن) :/ {team_data['sales']:,} ج\n"
            report += f"ROAS :/ {team_data['roas']:.2f}\n"
            report += "ــــــــــــــــــــــــــــــــــــــــــــ\n"
        else:
            report += f"عدد الاوردرات:/ {team_data['orders']}\n"
            report += f"المبيعات (غير شاملة الشحن) :/ {team_data['sales']:,} ج\n"

    
    a_data = data['A']
    b_data = data['B']
    
    ab_spend = a_data['spend'] + b_data['spend']
    ab_orders = a_data['orders'] + b_data['orders']
    ab_sales = a_data['sales'] + b_data['sales']
    ab_roas = ab_sales / ab_spend if ab_spend > 0 else 0
    ab_cost_per_order = ab_spend / ab_orders if ab_orders > 0 else 0
    
    report += "\nــــــــــــــــــــــــــــــــــــــــــــ\n"
    report += "اجماليات (A) + (B)\n"
    report += f"توتال الصرف الاوردرات ( إجمالي ) :/ {ab_spend:,} ج\n"
    report += f"إجمالي عام اوردات :/ {ab_orders}\n"
    report += f"التكلفة / {ab_cost_per_order:.2f} ج\n"
    report += f"إجمالي المبيعات (A+B) :/ {ab_sales:,} ج\n"
    report += f"ROAS (A+B) :/ {ab_roas:.2f}\n\n"
    
    c_data = data['C']
    c1_data = data['C1']

    cc1_spend = c_data['spend'] + c1_data['spend']
    cc1_orders = c_data['orders'] + c1_data['orders']
    cc1_sales = c_data['sales'] + c1_data['sales']
    cc1_roas = cc1_sales / cc1_spend if cc1_spend > 0 else 0
    cc1_cost_per_order = cc1_spend / cc1_orders if cc1_orders > 0 else 0

    report += "ــــــــــــــــــــــــــــــــــــــــــــ\n"
    report += "اجماليات (C) + (C1)\n"
    report += f"توتال الصرف الاوردرات ( إجمالي ) :/ {cc1_spend:,} ج\n"
    report += f"إجمالي عام اوردات :/ {cc1_orders}\n"
    report += f"التكلفة / {cc1_cost_per_order:.2f} ج\n"
    report += f"إجمالي المبيعات (C+C1) :/ {cc1_sales:,} ج\n"
    report += f"ROAS (C+C1) :/ {cc1_roas:.2f}\n\n"

    total_spend = sum(team_data['spend'] for team_data in data.values() if team_data['spend'] is not None)
    total_orders = sum(team_data['orders'] for team_data in data.values() if team_data['orders'] is not None)
    total_sales = sum(team_data['sales'] for team_data in data.values() if team_data['sales'] is not None)
    total_roas = total_sales / total_spend if total_spend > 0 else 0
    total_cost_per_order = total_spend / total_orders if total_orders > 0 else 0
    
    report += "ــــــــــــــــــــــــــــــــــــــــــــ\n"
    report += "اجماليات عامة\n"
    report += f"إجمالي الصرف الكلي :/ {total_spend:,} ج\n"
    report += f"إجمالي الأوردرات الكلي :/ {total_orders}\n"
    report += f"متوسط التكلفة الكلي :/ {total_cost_per_order:.2f} ج\n"
    report += f"إجمالي المبيعات الكلي :/ {total_sales:,} ج\n"
    report += f"ROAS الكلي :/ {total_roas:.2f}\n"
    
    return report

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)


