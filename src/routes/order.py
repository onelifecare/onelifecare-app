from flask import Blueprint, request, jsonify
import re
import openai

order_bp = Blueprint("order", __name__)

# Fallback parsing function (if ChatGPT fails or is not used)
def parse_order_text_fallback(text):
    total_amount = 0
    order_count = 0

    # Regex to find numbers that could be order counts or amounts
    # This is a very basic fallback and might need refinement
    numbers = re.findall(r'\d+', text)
    
    # Assuming each number found could represent an order or an amount
    # This logic needs to be improved based on actual order text patterns
    order_count = len(numbers) # Simplistic: count every number as an order
    if numbers:
        total_amount = sum(int(n) for n in numbers) # Simplistic: sum all numbers as amount

    return total_amount, order_count

# Function to parse order text using ChatGPT
def parse_order_text_with_chatgpt(order_text):
    try:
        # Placeholder for actual ChatGPT API call
        # You would send the order_text to ChatGPT and parse its response
        # For now, let's simulate a response or use a simple parsing logic
        
        # Example: Simulating ChatGPT response
        # response = openai.Completion.create(
        #     engine="text-davinci-003",
        #     prompt=f"Extract total amount and order count from the following text: {order_text}",
        #     max_tokens=100
        # )
        # parsed_data = response.choices[0].text.strip()
        
        # For demonstration, let's use a simple regex to extract numbers
        # This needs to be replaced with actual ChatGPT parsing
        numbers = re.findall(r'\d+', order_text)
        total_amount = sum(int(n) for n in numbers) if numbers else 0
        order_count = len(numbers) # Very basic, needs improvement with ChatGPT

        return total_amount, order_count
    except Exception as e:
        print(f"Error calling ChatGPT API: {e}")
        return 0, 0 # Return 0,0 on error to trigger fallback

@order_bp.route("/save_orders", methods=["POST"])
def save_orders_route():
    try:
        data = request.get_json()
        team = data.get("team", "")
        orders_text = data.get("orders", "")

        if not team or not orders_text.strip():
            return jsonify({"error": "الرجاء اختيار الفريق وإدخال نصوص الأوردرات."}), 400

        total_amount, order_count = parse_order_text_with_chatgpt(orders_text)
        if order_count == 0:
            total_amount, order_count = parse_order_text_fallback(orders_text)

        # Here you would save to your database
        # For now, just return a success message
        return jsonify({"message": f"تم حفظ {order_count} أوردرات بنجاح!", "orders_saved": order_count}), 200
    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

@order_bp.route("/process_orders", methods=["POST"])
def process_orders_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        # Placeholder for actual order processing logic
        # This is where you would integrate with ChatGPT or other services
        # For now, just return a success message
        return jsonify({"message": "Orders received and processed successfully!", "data": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


