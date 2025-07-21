import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
import pytz
import sqlite3
import re
import requests
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# Get the absolute path of the directory containing this script
basedir = os.path.abspath(os.path.dirname(__file__))

from whitenoise import WhiteNoise

app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'templates'))

app.wsgi_app = WhiteNoise(app.wsgi_app, root=os.path.join(basedir, 'static'))
app.wsgi_app.add_files(os.path.join(basedir, 'templates'), prefix='templates/')

def get_db_path():
    """الحصول على المسار المطلق لقاعدة البيانات في مجلد tmp"""
    return os.path.join(basedir, 'orders.db') # Changed to be in the same directory as the app

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
    """الحصول على اتصال بقاعدة البيانات مع التأكد من وجود الجداول"""
    init_db()
    return sqlite3.connect(get_db_path())

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/api/save_orders', methods=['POST'])
def save_orders():
    try:
        data = request.get_json()
        team = data.get('team', '')
        orders_text = data.get('orders', '')
        
        if not team or not orders_text.strip():
            return jsonify({'error': 'الرجاء اختيار الفريق وإدخال نصوص الأوردرات.'}), 400

        parsed_orders = parse_orders(orders_text)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Aggregate orders by team from parsed_orders
        team_order_counts = {}
        for order in parsed_orders:
            # Assuming the team is passed from the frontend and is consistent for the batch
            # If individual orders can have different teams, this logic needs adjustment
            team_order_counts[team] = team_order_counts.get(team, 0) + 1

        for team_name, count in team_order_counts.items():
            if count > 0:
                cursor.execute('INSERT INTO orders (team, order_count) VALUES (?, ?)', (team_name, count))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'تم حفظ {len(parsed_orders)} أوردرات بنجاح!', 'orders_saved': len(parsed_orders)}), 200
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

def load_facebook_access_token():
    """قراءة مفتاح الوصول لـ Facebook من الملف"""
    try:
        token_file_path = os.path.join(basedir, 'facebook_access_token.txt')
        with open(token_file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading Facebook access token: {e}")
        return None

def load_ad_account_ids():
    """قراءة معرفات الحسابات الإعلانية من الملف"""
    try:
        ids_file_path = os.path.join(basedir, 'ad_account_ids.txt')
        ad_accounts = {}
        with open(ids_file_path, 'r') as f:
            for line in f:
                if ':' in line:
                    team, account_id = line.strip().split(': ')
                    ad_accounts[team] = account_id
        return ad_accounts
    except Exception as e:
        print(f"Error loading ad account IDs: {e}")
        return {
            "A": "act_876940394061784",
            "B": "act_1063536228108993", 
            "C": "act_1256754798336209",
            "C1": "act_652648836844418"
        }

def get_facebook_ads_data():
    """سحب بيانات الصرف الحقيقية من Facebook Ads API"""
    data = {
        "A": {"spend": 0, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "B": {"spend": 0, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "C": {"spend": 0, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "C1": {"spend": 0, "orders": 0, "held": 0, "sales": 0, "roas": 0},
        "Follow-up": {"spend": 0, "orders": 0, "held": 0, "sales": 0, "roas": 0}
    }

    # تحميل مفتاح الوصول ومعرفات الحسابات
    access_token = load_facebook_access_token()
    ad_account_ids = load_ad_account_ids()
    
    if not access_token:
        print("No Facebook access token found, using dummy data")
        return data

    # تهيئة Facebook Ads API
    try:
        FacebookAdsApi.init(access_token=access_token)
    except Exception as e:
        print(f"Error initializing Facebook Ads API: {e}")
        return data

    # سحب بيانات الصرف لكل فريق
    for team, ad_account_id in ad_account_ids.items():
        if team in data:  # التأكد من أن الفريق موجود في البيانات
            try:
                account = AdAccount(ad_account_id)
                # سحب بيانات اليوم الحالي
                today = datetime.now().strftime("%Y-%m-%d")
                insights = account.get_insights(
                    fields=["spend"],
                    params={
                        "time_range": {"since": today, "until": today}
                    }
                )
                
                if insights and len(insights) > 0:
                    spend_value = insights[0].get("spend", "0")
                    data[team]["spend"] = float(spend_value)
                    print(f"Successfully fetched spend for {team}: {spend_value}")
                else:
                    print(f"No insights data found for {team} ({ad_account_id})")
                    
            except Exception as e:
                print(f"Error fetching data for {team} ({ad_account_id}): {e}")
                # في حالة الخطأ، نحتفظ بالقيمة الافتراضية 0

    return data

@app.route('/api/generate_report', methods=['GET'])
def generate_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # جلب إجمالي الأوردرات لكل فريق
        cursor.execute('SELECT team, SUM(order_count) FROM orders GROUP BY team ORDER BY team')
        orders_by_team = dict(cursor.fetchall())
        
        conn.close()

        # Get simplified Facebook Ads data
        facebook_data = get_facebook_ads_data()
        
        # Update facebook_data with actual orders from DB
        for team in facebook_data:
            facebook_data[team]["orders"] = orders_by_team.get(team, 0)

        # Calculate sales and held based on orders and dummy spend
        for team_name, data in facebook_data.items():
            # Assuming an average sale value per order for simplification
            # This needs to be adjusted based on actual business logic
            if team_name != 'Follow-up':
                data['sales'] = data['orders'] * 100 # Example: 100 JOD per order
                data['held'] = data['spend'] / data['orders'] if data['orders'] > 0 else 0
                data['roas'] = data['sales'] / data['spend'] if data['spend'] > 0 else 0
            else:
                data['sales'] = data['orders'] * 80 # Example: 80 JOD per order for follow-up

        # تنسيق التقرير
        report_text = format_detailed_report(facebook_data)
        
        return jsonify({
            "success": True,
            "report": report_text,
            "api_error": None
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": f"حدث خطأ: {str(e)}"}), 500

def parse_orders(order_text):
    parsed_orders = []
    # Split the input text into potential order blocks based on common separators
    # This regex looks for 'الاسم :' or multiple newlines as separators
    order_blocks = re.split(r'(?:الاسم :|\n\s*\n)+', order_text)

    for order_block in order_blocks:
        order_block = order_block.strip()
        if not order_block:
            continue

        # Extract 'الاسم' (Name)
        name_match = re.search(r'الاسم :\s*(.+?)(?:\n|$)', order_block)
        customer_name = name_match.group(1).strip() if name_match else "Unknown Customer"

        # Extract 'المبلغ' (Amount)
        # This regex now correctly handles 'ج' or 'م.ش' and optional '+' for multiple amounts
        amount_match = re.search(r'المبلغ :\s*([\d.,]+(?:\s*ج|م.ش)?)(?:\s*\+\s*([\d.,]+(?:\s*ج|م.ش)?))?', order_block)
        amount = 0.0
        if amount_match:
            amount_str_part1 = amount_match.group(1).replace('ج', '').replace('م.ش', '').replace(' ', '').replace(',', '')
            try:
                amount = float(amount_str_part1)
                if amount_match.group(2):
                    amount_str_part2 = amount_match.group(2).replace('ج', '').replace('م.ش', '').replace(' ', '').replace(',', '')
                    amount += float(amount_str_part2)
            except ValueError:
                print(f"Could not parse amount from: {amount_str_part1}")

        if amount > 0:
            parsed_orders.append({"customer_name": customer_name, "price": amount})
        else:
            print(f"Skipping order for {customer_name} due to invalid or missing amount.")

    return parsed_orders

def format_detailed_report(data):
    """تنسيق التقرير المفصل حسب المثال المعطى"""
    cairo_tz = pytz.timezone('Africa/Cairo')
    now = datetime.now(cairo_tz)
    
    # إضافة التاريخ والوقت في أعلى التقرير مع فاصل أقصر
    report = f'تاريخ التقرير: {now.strftime("%Y-%m-%d")}\n'
    report += f'الوقت: {now.strftime("%I:%M %p")}\n'
    report += "===================\n\n"
    
    # تفاصيل كل فريق
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

    
    # إجماليات A + B
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
    
    # إجماليات C + C1
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

    # إجماليات عامة
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



# A small change to force Heroku rebuild

