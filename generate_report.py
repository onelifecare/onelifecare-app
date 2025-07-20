from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
import datetime
import re
import pytz
import os

# Read Access Tokens from both Business Managers
access_tokens = {}
with open("/home/ubuntu/order_input_app/facebook_access_tokens.txt", "r") as f:
    for line in f:
        line = line.strip()
        if line and ": " in line:
            business, token = line.split(": ", 1)
            access_tokens[business] = token

# Read Ad Account IDs and map them to Business Managers
ad_account_mapping = {}
with open("/home/ubuntu/order_input_app/ad_account_ids.txt", "r") as f:
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
    timestamp_pattern = r'\[‏\d+‏/\d+‏/\d+،\s*\d+:\d+:\d+\s*[صم]\]\s*~?\s*[^:]+:'
    
    # Split the text by timestamps
    order_blocks = re.split(timestamp_pattern, whatsapp_text)
    
    # Remove empty blocks and process each order
    for block in order_blocks:
        block = block.strip()
        if block and len(block) > 50:  # Filter out very short blocks
            # Clean up the block by removing WhatsApp editing markers
            block = re.sub(r'‏<تم تعديل هذه الرسالة>', '', block)
            orders.append(block)
    
    return orders

def parse_order_text(order_text):
    """
    Parse individual order text to extract sales amount and agent name
    """
    sales_amount = 0
    agent_name = ""
    
    # Extract 'المبلغ' - look for patterns like "المبلغ : 1890+ 75م.ش" or "المبلغ : 1190 + 65"
    amount_patterns = [
        r'المبلغ\s*:\s*([\d,\.]+)\s*\+?\s*([\d,\.]*)\s*م\.ش',  # Pattern with م.ش
        r'المبلغ\s*:\s*([\d,\.]+)\s*\+\s*([\d,\.]+)',         # Pattern with +
        r'المبلغ\s*:\s*([\d,\.]+)\s*\+\s*([\d,\.]+)\s*شحن',   # Pattern with شحن
        r'المبلغ\s*:\s*([\d,\.]+)'                            # Simple pattern
    ]
    
    for pattern in amount_patterns:
        amount_match = re.search(pattern, order_text)
        if amount_match:
            product_price = float(amount_match.group(1).replace(',', ''))
            sales_amount = product_price  # Sales excluding shipping
            break

    # Extract 'الايچينت' or 'الايچينت :'
    agent_patterns = [
        r'الايچينت\s*:\s*(.+?)(?:\n|$)',
        r'الايچينت\s*:\s*(.+?)(?:\s|$)'
    ]
    
    for pattern in agent_patterns:
        agent_match = re.search(pattern, order_text)
        if agent_match:
            agent_name = agent_match.group(1).strip()
            # Clean up agent name
            agent_name = re.sub(r'‏<تم تعديل هذه الرسالة>', '', agent_name)
            break
        
    return sales_amount, agent_name

def generate_report():
    # Read order texts from files
    orders_dir = '/home/ubuntu/order_input_app/orders'
    order_texts_by_team = {
        'Team A': [],
        'Team B': [],
        'Team C': [],
        'Team C1': [],
        'Team Follow-up': []
    }
    
    # Load orders from files
    if os.path.exists(orders_dir):
        for team_file in os.listdir(orders_dir):
            if team_file.endswith('.txt'):
                team_name = f"Team {team_file[:-4]}"
                if team_name == "Team فولو أب":
                    team_name = "Team Follow-up"
                
                file_path = os.path.join(orders_dir, team_file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        order_texts_by_team[team_name] = [content]
    # Define time range (today from midnight) in Egypt timezone
    egypt_tz = pytz.timezone('Africa/Cairo')
    now = datetime.datetime.now(egypt_tz)
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

    for team, order_texts in order_texts_by_team.items():
        for order_text in order_texts:
            # Parse WhatsApp orders if the text contains multiple orders
            if '[‏' in order_text and '~' in order_text:
                # This is WhatsApp text with multiple orders
                individual_orders = parse_whatsapp_orders(order_text)
                for individual_order in individual_orders:
                    sales_amount, _ = parse_order_text(individual_order)
                    if sales_amount > 0:  # Only count valid orders
                        team_sales_data[team]['orders'] += 1
                        team_sales_data[team]['sales'] += sales_amount
            else:
                # This is a single order
                sales_amount, _ = parse_order_text(order_text)
                if sales_amount > 0:  # Only count valid orders
                    team_sales_data[team]['orders'] += 1
                    team_sales_data[team]['sales'] += sales_amount

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
        report += "  ________________\n"
        overall_total_orders += follow_up_orders
        overall_total_sales += follow_up_sales

    # Add totals section for A+B
    if total_orders_ab > 0:
        total_cost_per_order_ab = total_spend_ab / total_orders_ab
    else:
        total_cost_per_order_ab = 0
    
    report += "________👇اجماليات 👇_____\n"
    report += "(A) + (B)\n"
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
    
    report += "\n(C) + (C1)\n"
    report += f"توتال الصرف الاوردرات ( إجمالي ) :/ {total_spend_cc1:,.0f}\n"
    report += f"إجمالي عام اوردات :/ {total_orders_cc1}\n"
    report += f"ممسوك / {total_cost_per_order_cc1:,.0f}\n"
    report += f"إجمالي المبيعات (C+C1) :/ {total_sales_cc1:,.0f}\n"
    roas_cc1 = total_sales_cc1 / total_spend_cc1 if total_spend_cc1 > 0 else 0
    report += f"ROAS (C+C1) :/ {roas_cc1:.2f}\n"

    # Add overall totals
    overall_cost_per_order = overall_total_spend / overall_total_orders if overall_total_orders > 0 else 0
    overall_roas = overall_total_sales / overall_total_spend if overall_total_spend > 0 else 0

    report += "\n________👇اجماليات عامة 👇_____\n"
    report += f"إجمالي الصرف الكلي :/ {overall_total_spend:,.0f}\n"
    report += f"إجمالي الأوردرات الكلي :/ {overall_total_orders}\n"
    report += f"متوسط ممسوك الكلي :/ {overall_cost_per_order:,.0f}\n"
    report += f"إجمالي المبيعات الكلي :/ {overall_total_sales:,.0f}\n"
    report += f"ROAS الكلي :/ {overall_roas:.2f}\n"

    return report

if __name__ == "__main__":
    # Test with the provided WhatsApp text
    test_whatsapp_text = """[‏17‏/7‏/2025، 12:37:42 ص] ~ روان محمود: الاسم : عوض سعد الحداد
المبلغ : 1890+ 75م.ش 
الايچينت : روان
[‏17‏/7‏/2025، 2:07:56 ص] ~ روان محمود: الاسم :مي أشرف ابراهيم 
المبلغ : 1190 + 65 
الايچينت : روان"""

    dummy_order_texts_by_team = {
        "Team A": [test_whatsapp_text],
        "Team B": [],
        "Team C": [],
        "Team C1": [],
        "Team Follow-up": []
    }

    report = generate_report(dummy_order_texts_by_team)
    print(report)
    
    # Save report to file
    with open("latest_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

