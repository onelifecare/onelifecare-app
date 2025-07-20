from flask import Blueprint, jsonify, request
import os
import re
from datetime import datetime

user_bp = Blueprint('user', __name__)

def clean_whatsapp_text(text):
    """Clean WhatsApp text by removing timestamps, names, and other metadata"""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip WhatsApp metadata lines (timestamps, names, etc.)
        # Common patterns: "17/07/2025, 11:27 PM - Name:"
        if re.match(r'\d{1,2}/\d{1,2}/\d{4},\s*\d{1,2}:\d{2}\s*(AM|PM)\s*-', line):
            continue
        if re.match(r'\d{1,2}:\d{2}\s*(AM|PM)\s*-', line):
            continue
        if line.startswith('~') or line.startswith('You'):
            continue
        if 'joined using this group' in line or 'left' in line:
            continue
        if line.startswith('<Media omitted>') or line.startswith('This message was deleted'):
            continue
            
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def parse_orders(text):
    """Parse orders from cleaned text"""
    if not text or not text.strip():
        return []
    
    # Clean WhatsApp metadata first
    cleaned_text = clean_whatsapp_text(text)
    
    orders = []
    current_order = {}
    
    lines = cleaned_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            # If we have a complete order, save it
            if current_order and 'name' in current_order and 'amount' in current_order:
                orders.append(current_order)
                current_order = {}
            continue
        
        # Parse order fields
        if 'الاسم' in line or 'الأسم' in line or 'اسم' in line:
            # Save previous order if complete
            if current_order and 'name' in current_order and 'amount' in current_order:
                orders.append(current_order)
                current_order = {}
            
            # Extract name
            name_match = re.search(r'(?:الاسم|الأسم|اسم)\s*[:：]\s*(.+)', line)
            if name_match:
                current_order['name'] = name_match.group(1).strip()
        
        elif 'المبلغ' in line or 'مبلغ' in line:
            # Extract amount
            amount_match = re.search(r'(?:المبلغ|مبلغ)\s*[:：]\s*(.+)', line)
            if amount_match:
                amount_text = amount_match.group(1).strip()
                # Extract numbers from amount (product price + shipping)
                numbers = re.findall(r'\d+', amount_text)
                if numbers:
                    # First number is usually the product price
                    current_order['amount'] = int(numbers[0])
                    current_order['amount_text'] = amount_text
        
        elif 'الايچينت' in line or 'ايچينت' in line or 'الإيجنت' in line:
            # Extract agent
            agent_match = re.search(r'(?:الايچينت|ايچينت|الإيجنت)\s*[:：]\s*(.+)', line)
            if agent_match:
                current_order['agent'] = agent_match.group(1).strip()
    
    # Don't forget the last order
    if current_order and 'name' in current_order and 'amount' in current_order:
        orders.append(current_order)
    
    return orders

@user_bp.route('/api/save_orders', methods=['POST'])
def save_orders():
    try:
        data = request.get_json()
        team = data.get('team')
        orders_text = data.get('orders')
        
        if not team or not orders_text:
            return jsonify({'error': 'Team and orders are required'}), 400
        
        # Parse orders from text
        orders = parse_orders(orders_text)
        
        if not orders:
            return jsonify({'error': 'No valid orders found in the text'}), 400
        
        # Create orders directory if it doesn't exist
        orders_dir = '/home/ubuntu/order_input_app/orders'
        os.makedirs(orders_dir, exist_ok=True)
        
        # Save orders to team-specific file
        team_file = os.path.join(orders_dir, f'{team}.txt')
        
        # Append new orders to existing file
        with open(team_file, 'a', encoding='utf-8') as f:
            for order in orders:
                f.write(f"الاسم: {order.get('name', 'غير محدد')}\n")
                f.write(f"المبلغ: {order.get('amount_text', order.get('amount', 0))}\n")
                f.write(f"الايچينت: {order.get('agent', 'غير محدد')}\n")
                f.write("---\n")
        
        return jsonify({
            'message': f'Successfully saved {len(orders)} orders for {team}',
            'orders_count': len(orders)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/clear_data', methods=['POST'])
def clear_data():
    try:
        # Clear all order files
        orders_dir = '/home/ubuntu/order_input_app/orders'
        if os.path.exists(orders_dir):
            for filename in os.listdir(orders_dir):
                file_path = os.path.join(orders_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        
        return jsonify({'message': 'تم مسح جميع البيانات بنجاح'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/api/generate_report')
def generate_report():
    try:
        # Import and run the report generation
        import sys
        sys.path.append('/home/ubuntu/order_input_app')
        
        from generate_report import generate_report as gen_report
        report = gen_report()
        
        return jsonify({'report': report})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

