import os
import re
import json
from flask import Blueprint, request, jsonify
from src.models.order import Order
from src.models.user import db
from openai import OpenAI

order_bp = Blueprint("order", __name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_API_BASE"))

def parse_order_text_with_chatgpt(order_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Using gpt-4o as discussed
            messages=[
                {"role": "system", "content": "You are an order parsing assistant. Extract the total amount (including shipping) and the number of orders from the given text. If multiple orders are present, sum their amounts and count them. Respond only with a JSON object like: {\"total_amount\": float, \"order_count\": int}. If no amount is found, return 0 for total_amount. If no orders are found, return 0 for order_count."},
                {"role": "user", "content": order_text}
            ],
            response_format={"type": "json_object"}
        )
        parsed_data = response.choices[0].message.content
        data = json.loads(parsed_data)
        return data.get("total_amount", 0.0), data.get("order_count", 0)
    except Exception as e:
        print(f"Error parsing with ChatGPT: {e}")
        return 0.0, 0

def parse_order_text_fallback(order_text):
    total_amount = 0.0
    order_count = 0

    # البحث عن الطوابع الزمنية لعد الأوردرات
    timestamp_pattern = r"\n\[\d{1,2}/\d{1,2}, \d{1,2}:\d{2}\s*[AP]M\]"
    orders = re.split(timestamp_pattern, order_text)
    # أول عنصر في القائمة سيكون ما قبل أول طابع زمني، لذا نتجاهله
    order_count = len(orders) - 1
    
    # البحث عن المبالغ
    amount_patterns = [
        r"المبلغ\s*:\s*(\d+)\s*\+\s*(\d+)",  # المبلغ : 1190 + 65
        r"المبلغ\s*:\s*(\d+)\s*\+\s*(\d+)\s*شحن",  # المبلغ : 1190 + 65 شحن
        r"المبلغ\s*:\s*(\d+)\s*\+\s*(\d+)\s*م\.ش",  # المبلغ : 1890+ 75م.ش
        r"المبلغ\s*:\s*(\d+)\s*السعر\s*بالشحن",  # المبلغ : 2025 السعر بالشحن
        r"المبلغ\s*:\s*(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)",  # المبلغ : 1890 + 1600 + 75
    ]
    
    for pattern in amount_patterns:
        matches = re.findall(pattern, order_text)
        for match in matches:
            if len(match) == 2:  # نمط بمبلغين
                amount1 = int(match[0])
                amount2 = int(match[1])
                total = amount1 + amount2
                total_amount += total
            elif len(match) == 3:  # نمط بثلاثة مبالغ
                amount1 = int(match[0])
                amount2 = int(match[1])
                amount3 = int(match[2])
                total = amount1 + amount2 + amount3
                total_amount += total
            elif len(match) == 1:  # نمط بمبلغ واحد (السعر بالشحن)
                amount = int(match[0])
                total_amount += amount

    return total_amount, order_count

@order_bp.route("/process_orders", methods=["POST"])
def process_orders():
    data = request.get_json()
    order_text = data.get("order_text")
    team_name = data.get("team_name")

    total_amount, order_count = parse_order_text_with_chatgpt(order_text)

    if order_count == 0:
        total_amount, order_count = parse_order_text_fallback(order_text)

    # Optionally, save to database here if needed, but for now just return the parsed data
    return jsonify({"total_amount": total_amount, "order_count": order_count})


