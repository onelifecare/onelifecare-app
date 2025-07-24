import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime
import pytz
import sqlite3
import re
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# Get the absolute path of the directory containing this script
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'templates'))

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

        parsed_orders = parse_orders(orders_text)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        team_order_counts = {}
        for order in parsed_orders:
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



@app.route("/api/generate_report", methods=["GET"])
def generate_report_route():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT team, SUM(order_count) FROM orders GROUP BY team ORDER BY team')
        orders_by_team = dict(cursor.fetchall())
        
        conn.close()
        report_text = generate_report_data_and_format()
        return jsonify({
            "success": True,
            "report": report_text,
            "api_error": None
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": f"حدث خطأ: {str(e)}"}), 500

def parse_orders(order_text):
    parsed_orders = []
    # Check if the input text is a WhatsApp chat export
    if '[‏' in order_text and '~' in order_text:
        individual_orders = parse_whatsapp_orders(order_text)
        for individual_order in individual_orders:
            sales_amount, _ = parse_order_text(individual_order)
            if sales_amount > 0:
                parsed_orders.append({"price": sales_amount})
    else:
        # Assume it's a single order if not a WhatsApp chat
        sales_amount, _ = parse_order_text(order_text)
        if sales_amount > 0:
            parsed_orders.append({"price": sales_amount})
    return parsed_orders

def format_detailed_report(data):
    cairo_tz = pytz.timezone('Africa/Cairo')
    now = datetime.now(cairo_tz)
    
    report = f"تاريخ التقرير: {now.strftime('%Y-%m-%d')}\n"
    report += f'الوقت: {now.strftime("%I:%M %p")}\n'
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
    port = int(os.environ.get('PORT', 5000))
    init_db()
    app.run(debug=False, host='0.0.0.0', port=port)





# Functions from generate_report.py

# Read Access Tokens from both Business Managers
access_tokens = {}
# Update path to reflect the new location
with open("/app/facebook_access_tokens.txt", "r") as f:
    for line in f:
        line = line.strip()
        if line and ": " in line:
            business, token = line.split(": ", 1)
            access_tokens[business] = token

# Read Ad Account IDs and map them to Business Managers
ad_account_mapping = {}
# Update path to reflect the new location
with open("/app/ad_account_ids.txt", "r") as f:
    for line in f:
        line = line.strip()
        if line and ": " in line:
            team, account_id = line.split(": ")
            # Map teams to their respective Business Managers
            # Business 1: Team A, B, C
            # Business 2: Team C1
            if team == "Team C1":
                ad_account_mapping[team] = {"account_id": account_id, "business": "Business2"}
            else:  # Teams A, B, C are in Business1
                ad_account_mapping[team] = {"account_id": account_id, "business": "Business1"}

def get_ad_spend_multi_business(team, start_time, end_time):
    try:
        if team not in ad_account_mapping:
            print(f"Team {team} not found in mapping")
            return 0
            
        account_info = ad_account_mapping[team]
        account_id = account_info["account_id"]
        business = account_info["business"]
        
        if business not in access_tokens:
            print(f"Access token for {business} not found")
            return 0
            
        # Initialize Facebook API with the appropriate token
        FacebookAdsApi.init(access_token=access_tokens[business])
        
        account = AdAccount(account_id)
        params = {
            "time_range": {
                "since": start_time.strftime("%Y-%m-%d"),
                "until": end_time.strftime("%Y-%m-%d")
            },
            "time_increment": 1,
            "fields": ["spend"]
        }
        insights = account.get_insights(params=params)
        total_spend = 0
        for insight in insights:
            total_spend += float(insight["spend"])
        return total_spend
    except Exception as e:
        print(f"Error fetching spend for {team} ({account_id}): {e}")
        return 0

def parse_whatsapp_orders(whatsapp_text):
    """
    Parse WhatsApp text containing multiple orders separated by timestamps and sender names
    """
    orders = []
    
    # Split by WhatsApp timestamp pattern [date, time] ~ sender:
    # Pattern: [‏17‏/7‏/2025، 12:37:42 ص] ~ sender name:
    # Updated pattern to be more flexible with unicode characters and spaces
    timestamp_pattern = r"\u200f?\[\u200f?\d+\u200f?\/\u200f?\d+\u200f?\/\u200f?\d+،?\s*\d+:\d+:\d+\s*[صم]\u200f?\]\s*~?\s*[^:]+:\s*"
    
    # Split the text by timestamps
    order_blocks = re.split(timestamp_pattern, whatsapp_text)
    
    # Remove empty blocks and process each order
    for block in order_blocks:
        block = block.strip()
        if block and len(block) > 50:  # Filter out very short blocks
            # Clean up the block by removing WhatsApp editing markers
            block = re.sub(r"\u200f<تم تعديل هذه الرسالة>", "", block)
            orders.append(block)
    
    return orders

def parse_order_text(order_text):
    """
    Parse individual order text to extract sales amount and agent name
    Improved version to handle more patterns including multiple additions
    """
    sales_amount = 0
    agent_name = ""
    
    print(f"DEBUG: Processing order text (first 200 chars): {order_text[:200]}...")
    
    # Extract 'المبلغ' - look for various patterns
    amount_patterns = [
        # Pattern with multiple additions: "1190 + 250 + 150"
        r"المبلغ\s*:\s*([\d,\.]+(?:\s*\+\s*[\d,\.]+)*)",
        # Pattern with م.ش: "1890+ 75م.ش" or "1890 + 75 م.ش"
        r"المبلغ\s*:\s*([\d,\.]+)\s*\+?\s*([\d,\.]*)\s*م\.ش",
        # Pattern with شحن: "1190 + 75 شحن"
        r"المبلغ\s*:\s*([\d,\.]+)\s*\+\s*([\d,\.]+)\s*شحن",
        # Pattern with +: "1190 + 65"
        r"المبلغ\s*:\s*([\d,\.]+)\s*\+\s*([\d,\.]+)",
        # Simple pattern: "1190"
        r"المبلغ\s*:\s*([\d,\.]+)",
    ]
    
    for i, pattern in enumerate(amount_patterns):
        amount_match = re.search(pattern, order_text)
        if amount_match:
            print(f"DEBUG: Pattern {i} matched: {amount_match.group(0)}")
            
            if i == 0:  # Multiple additions pattern
                # Extract all numbers and sum them
                numbers = re.findall(r'[\d,\.]+', amount_match.group(1))
                total = 0
                for num in numbers:
                    total += float(num.replace(",", ""))
                sales_amount = total
                print(f"DEBUG: Multiple additions - numbers: {numbers}, total: {total}")
            else:
                # Single number pattern
                product_price = float(amount_match.group(1).replace(",", ""))
                sales_amount = product_price  # Sales excluding shipping
                print(f"DEBUG: Single number - price: {product_price}")
            break
    
    if sales_amount == 0:
        print("DEBUG: No amount pattern matched")

    # Extract \'الايچينت\' or \'الايچينت :\'
    agent_patterns = [
        r"الايچينت\s*:\s*(.+?)(?:\n|$)",
        r"الايچينت\s*:\s*(.+?)(?:\s|$)"
    ]
    
    for pattern in agent_patterns:
        agent_match = re.search(pattern, order_text)
        if agent_match:
            agent_name = agent_match.group(1).strip()
            # Clean up agent name
            agent_name = re.sub(r"\u200f<تم تعديل هذه الرسالة>", "", agent_name)
            print(f"DEBUG: Agent found: {agent_name}")
            break
    
    if not agent_name:
        print("DEBUG: No agent pattern matched")
        
    return sales_amount, agent_name







def generate_report_data_and_format():
    # Define time range (today from midnight) in Egypt timezone
    egypt_tz = pytz.timezone('Africa/Cairo')
    now = datetime.now(egypt_tz)
    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = now

    # Fetch spend for each team using multi-business approach
    ad_spend_data = {}
    for team in ["Team A", "Team B", "Team C", "Team C1"]:
        spend = get_ad_spend_multi_business(team, start_time, end_time)
        ad_spend_data[team] = spend

    # Process order texts to get sales and order counts
    team_sales_data = {
        'Team A': {'orders': 0, 'sales': 0},
        'Team B': {'orders': 0, 'sales': 0},
        'Team C': {'orders': 0, 'sales': 0},
        'Team C1': {'orders': 0, 'sales': 0},
        'Team Follow-up': {'orders': 0, 'sales': 0}
    }

    # Load orders from database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT team, SUM(order_count), SUM(sales) FROM orders GROUP BY team")
    db_orders = cursor.fetchall()
    conn.close()

    for team, count, sales in db_orders:
        if team in team_sales_data:
            team_sales_data[team]["orders"] += count if count else 0
            team_sales_data[team]["sales"] += sales if sales else 0

    # Generate report in the requested format with Egypt timezone and date
    report_date = now.strftime("%Y/%m/%d")
    report_time = now.strftime("%I:%M %p")
    report = f"* صرف يوم {report_date} الساعه {report_time}\n"
    report += " ---------------------------------\n"

    # Individual team reports and overall totals
    team_reports = []
    total_spend_ab = 0
    total_orders_ab = 0
    total_sales_ab = 0

    total_spend_cc1 = 0
    total_orders_cc1 = 0
    total_sales_cc1 = 0

    overall_total_spend = 0
    overall_total_orders = 0
    overall_total_sales = 0

    teams_to_report = ["Team A", "Team B", "Team C", "Team C1"]

    for team in teams_to_report:
        spend = ad_spend_data.get(team, 0)
        orders = team_sales_data.get(team, {}).get('orders', 0)
        sales = team_sales_data.get(team, {}).get('sales', 0)

        # Calculate "ممسوك" (Cost Per Order)
        cost_per_order = spend / orders if orders > 0 else 0

        # Calculate ROAS
        roas = sales / spend if spend > 0 else 0

        # Format team name for display
        team_display = team.replace("Team ", "تيم ")
        if team == "Team C1":
            team_display = "تيم (C1)"
        elif team == "Team C":
            team_display = "تيم (C)"
        elif team == "Team B":
            team_display = "تيم (B)"
        elif team == "Team A":
            team_display = "تيم (A)"

        team_report = f"{team_display}\n"
        team_report += f"الصرف :/ {spend:,.0f}\n"
        team_report += f"عدد الاوردرات / {orders}\n"
        team_report += f"ممسوك : / {cost_per_order:,.0f}\n"
        team_report += f"المبيعات (غير شاملة الشحن) :/ {sales:,.0f}\n"
        team_report += f"ROAS :/ {roas:.2f}\n"
        team_report += "ــــــــــــــــــــــــــــــــــــــــــــ\n"

        team_reports.append(team_report)

        # Calculate totals for A+B
        if team in ["Team A", "Team B"]:
            total_spend_ab += spend
            total_orders_ab += orders
            total_sales_ab += sales

        # Calculate totals for C+C1
        if team in ["Team C", "Team C1"]:
            total_spend_cc1 += spend
            total_orders_cc1 += orders
            total_sales_cc1 += sales

        # Calculate overall totals
        overall_total_spend += spend
        overall_total_orders += orders
        overall_total_sales += sales

    # Add team reports to main report
    for team_report in team_reports:
        report += team_report

    # Add Follow-up team (assuming no spend for follow-up)
    follow_up_orders = team_sales_data.get("Team Follow-up", {}).get('orders', 0)
    follow_up_sales = team_sales_data.get("Team Follow-up", {}).get('sales', 0)
    if follow_up_orders > 0:
        report += f"تيم (فولو أب)\n"
        report += f"عدد الاوردرات:/ {follow_up_orders}\n"
        report += f"المبيعات (غير شاملة الشحن) :/ {follow_up_sales:,.0f}\n"
        report += "ــــــــــــــــــــــــــــــــــــــــــــ\n"
        overall_total_orders += follow_up_orders
        overall_total_sales += follow_up_sales

    # Add totals section for A+B
    if total_orders_ab > 0:
        total_cost_per_order_ab = total_spend_ab / total_orders_ab
    else:
        total_cost_per_order_ab = 0

    report += "\nاجماليات (A) + (B)\n"
    report += f"توتال الصرف الاوردرات ( إجمالي ) :/ {total_spend_ab:,.0f}\n"
    report += f"إجمالي عام اوردات :/ {total_orders_ab}\n"
    report += f"ممسوك / {total_cost_per_order_ab:,.0f}\n"
    report += f"إجمالي المبيعات (A+B) :/ {total_sales_ab:,.0f}\n"
    roas_ab = total_sales_ab / total_spend_ab if total_spend_ab > 0 else 0
    report += f"ROAS (A+B) :/ {roas_ab:.2f}\n"

    # Add totals section for C+C1
    if total_orders_cc1 > 0:
        total_cost_per_order_cc1 = total_spend_cc1 / total_orders_cc1
    else:
        total_cost_per_order_cc1 = 0

    report += "\nاجماليات (C) + (C1)\n"
    report += f"توتال الصرف الاوردرات ( إجمالي ) :/ {total_spend_cc1:,.0f}\n"
    report += f"إجمالي عام اوردات :/ {total_orders_cc1}\n"
    report += f"ممسوك / {total_cost_per_order_cc1:,.0f}\n"
    report += f"إجمالي المبيعات (C+C1) :/ {total_sales_cc1:,.0f}\n"
    roas_cc1 = total_sales_cc1 / total_spend_cc1 if total_spend_cc1 > 0 else 0
    report += f"ROAS (C+C1) :/ {roas_cc1:.2f}\n"

    # Add overall totals
    overall_cost_per_order = overall_total_spend / overall_total_orders if overall_total_orders > 0 else 0
    overall_roas = overall_total_sales / overall_total_spend if overall_total_spend > 0 else 0

    report += "\nاجماليات عامة\n"
    report += f"إجمالي الصرف الكلي :/ {overall_total_spend:,.0f}\n"
    report += f"إجمالي الأوردرات الكلي :/ {overall_total_orders}\n"
    report += f"متوسط ممسوك الكلي :/ {overall_cost_per_order:,.0f}\n"
    report += f"إجمالي المبيعات الكلي :/ {overall_total_sales:,.0f}\n"
    report += f"ROAS الكلي :/ {overall_roas:.2f}\n"

    return report



