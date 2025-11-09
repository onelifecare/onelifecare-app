"""
وحدة تتبع البادجت الشغال (Running Budget Tracker)
تستخدم Facebook Ads API لجلب الحملات النشطة وحساب إجمالي البادجت
"""
import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign

def load_facebook_access_token():
    """قراءة مفتاح الوصول لـ Facebook من الملف"""
    try:
        basedir = os.path.abspath(os.path.dirname(__file__))
        token_file_path = os.path.join(basedir, 'facebook_access_token.txt')
        with open(token_file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading Facebook access token: {e}")
        return None

def load_ad_account_ids():
    """قراءة معرفات الحسابات الإعلانية من الملف"""
    try:
        basedir = os.path.abspath(os.path.dirname(__file__))
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
        return {}

def get_active_campaigns_budget():
    """
    جلب إجمالي البادجت للحملات النشطة في جميع الحسابات الإعلانية
    
    Returns:
        dict: قاموس يحتوي على بيانات البادجت لكل فريق
        {
            "A": {"daily_budget": 1000, "lifetime_budget": 0, "campaigns_count": 5},
            "B": {"daily_budget": 800, "lifetime_budget": 0, "campaigns_count": 3},
            ...
            "total": {"daily_budget": 3000, "lifetime_budget": 0, "campaigns_count": 15}
        }
    """
    result = {
        "A": {"daily_budget": 0, "lifetime_budget": 0, "campaigns_count": 0, "campaigns": []},
        "B": {"daily_budget": 0, "lifetime_budget": 0, "campaigns_count": 0, "campaigns": []},
        "C": {"daily_budget": 0, "lifetime_budget": 0, "campaigns_count": 0, "campaigns": []},
        "C1": {"daily_budget": 0, "lifetime_budget": 0, "campaigns_count": 0, "campaigns": []},
        "total": {"daily_budget": 0, "lifetime_budget": 0, "campaigns_count": 0}
    }
    
    # تحميل مفتاح الوصول ومعرفات الحسابات
    access_token = load_facebook_access_token()
    ad_account_ids = load_ad_account_ids()
    
    if not access_token:
        print("No Facebook access token found")
        return result
    
    # تهيئة Facebook Ads API
    try:
        FacebookAdsApi.init(access_token=access_token)
    except Exception as e:
        print(f"Error initializing Facebook Ads API: {e}")
        return result
    
    # جلب الحملات النشطة لكل حساب
    for team, ad_account_id in ad_account_ids.items():
        if team not in result:
            continue
            
        try:
            account = AdAccount(ad_account_id)
            
            # جلب الحملات النشطة فقط
            campaigns = account.get_campaigns(
                fields=[
                    Campaign.Field.id,
                    Campaign.Field.name,
                    Campaign.Field.status,
                    Campaign.Field.daily_budget,
                    Campaign.Field.lifetime_budget,
                    Campaign.Field.budget_remaining
                ],
                params={
                    'effective_status': ['ACTIVE']  # الحملات النشطة فقط
                }
            )
            
            team_daily_budget = 0
            team_lifetime_budget = 0
            campaign_list = []
            
            for campaign in campaigns:
                campaign_info = {
                    'id': campaign.get(Campaign.Field.id, ''),
                    'name': campaign.get(Campaign.Field.name, 'Unknown'),
                    'status': campaign.get(Campaign.Field.status, 'UNKNOWN')
                }
                
                # البادجت اليومي
                daily_budget = campaign.get(Campaign.Field.daily_budget)
                if daily_budget:
                    daily_budget_value = float(daily_budget) / 100  # Facebook API returns budget in cents
                    team_daily_budget += daily_budget_value
                    campaign_info['daily_budget'] = daily_budget_value
                else:
                    campaign_info['daily_budget'] = 0
                
                # البادجت الكلي
                lifetime_budget = campaign.get(Campaign.Field.lifetime_budget)
                if lifetime_budget:
                    lifetime_budget_value = float(lifetime_budget) / 100
                    team_lifetime_budget += lifetime_budget_value
                    campaign_info['lifetime_budget'] = lifetime_budget_value
                else:
                    campaign_info['lifetime_budget'] = 0
                
                # البادجت المتبقي
                budget_remaining = campaign.get(Campaign.Field.budget_remaining)
                if budget_remaining:
                    campaign_info['budget_remaining'] = float(budget_remaining) / 100
                else:
                    campaign_info['budget_remaining'] = 0
                
                campaign_list.append(campaign_info)
            
            # تحديث بيانات الفريق
            result[team]["daily_budget"] = team_daily_budget
            result[team]["lifetime_budget"] = team_lifetime_budget
            result[team]["campaigns_count"] = len(campaign_list)
            result[team]["campaigns"] = campaign_list
            
            # تحديث الإجمالي
            result["total"]["daily_budget"] += team_daily_budget
            result["total"]["lifetime_budget"] += team_lifetime_budget
            result["total"]["campaigns_count"] += len(campaign_list)
            
            print(f"Successfully fetched budget for {team}: {len(campaign_list)} active campaigns")
            
        except Exception as e:
            print(f"Error fetching campaigns for {team} ({ad_account_id}): {e}")
            # في حالة الخطأ، نحتفظ بالقيمة الافتراضية 0
    
    return result

def format_budget_report(budget_data):
    """
    تنسيق تقرير البادجت الشغال
    
    Args:
        budget_data: البيانات من get_active_campaigns_budget()
    
    Returns:
        str: تقرير منسق
    """
    report = "📊 تقرير البادجت الشغال (Running Budget)\n"
    report += "=" * 50 + "\n\n"
    
    teams = ["A", "B", "C", "C1"]
    
    for team in teams:
        team_data = budget_data[team]
        report += f"تيم ({team})\n"
        report += f"عدد الحملات النشطة: {team_data['campaigns_count']}\n"
        report += f"البادجت اليومي: {team_data['daily_budget']:,.2f} ج\n"
        
        if team_data['lifetime_budget'] > 0:
            report += f"البادجت الكلي: {team_data['lifetime_budget']:,.2f} ج\n"
        
        report += "-" * 50 + "\n"
    
    # الإجمالي
    total_data = budget_data["total"]
    report += "\n" + "=" * 50 + "\n"
    report += "الإجمالي الكلي\n"
    report += f"إجمالي عدد الحملات النشطة: {total_data['campaigns_count']}\n"
    report += f"إجمالي البادجت اليومي: {total_data['daily_budget']:,.2f} ج\n"
    
    if total_data['lifetime_budget'] > 0:
        report += f"إجمالي البادجت الكلي: {total_data['lifetime_budget']:,.2f} ج\n"
    
    report += "=" * 50 + "\n"
    
    return report

if __name__ == "__main__":
    # اختبار الوظيفة
    budget_data = get_active_campaigns_budget()
    print(format_budget_report(budget_data))
