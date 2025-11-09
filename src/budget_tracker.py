"""
Budget Tracker Module
Fetches and calculates running budget for active campaigns
"""
import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign


def get_active_campaigns_budget():
    """
    Get active campaigns and their budgets from all ad accounts
    Returns a dictionary with team data and totals
    """
    # Get the base directory
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # Read access token
    token_file = os.path.join(basedir, 'facebook_access_token.txt')
    with open(token_file, 'r') as f:
        access_token = f.read().strip()
    
    # Initialize Facebook Ads API
    FacebookAdsApi.init(access_token=access_token)
    
    # Read ad account IDs
    accounts_file = os.path.join(basedir, 'ad_account_ids.txt')
    with open(accounts_file, 'r') as f:
        lines = f.readlines()
    
    # Parse account IDs
    teams = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('=')
        if len(parts) == 2:
            team_name = parts[0].strip()
            account_id = parts[1].strip()
            teams[team_name] = account_id
    
    # Fetch campaign data for each team
    result = {}
    total_campaigns = 0
    total_daily_budget = 0
    
    for team_name, account_id in teams.items():
        try:
            account = AdAccount(account_id)
            
            # Get active campaigns
            campaigns = account.get_campaigns(
                fields=[
                    Campaign.Field.name,
                    Campaign.Field.status,
                    Campaign.Field.daily_budget,
                    Campaign.Field.lifetime_budget,
                ],
                params={
                    'effective_status': ['ACTIVE']
                }
            )
            
            team_data = {
                'campaigns': [],
                'campaigns_count': 0,
                'daily_budget': 0,
                'lifetime_budget': 0
            }
            
            for campaign in campaigns:
                campaign_info = {
                    'name': campaign.get(Campaign.Field.name, 'N/A'),
                    'status': campaign.get(Campaign.Field.status, 'N/A'),
                    'daily_budget': float(campaign.get(Campaign.Field.daily_budget, 0)) / 100 if campaign.get(Campaign.Field.daily_budget) else 0,
                    'lifetime_budget': float(campaign.get(Campaign.Field.lifetime_budget, 0)) / 100 if campaign.get(Campaign.Field.lifetime_budget) else 0
                }
                
                team_data['campaigns'].append(campaign_info)
                team_data['daily_budget'] += campaign_info['daily_budget']
                team_data['lifetime_budget'] += campaign_info['lifetime_budget']
            
            team_data['campaigns_count'] = len(team_data['campaigns'])
            total_campaigns += team_data['campaigns_count']
            total_daily_budget += team_data['daily_budget']
            
            result[team_name] = team_data
            
        except Exception as e:
            print(f"Error fetching data for {team_name}: {str(e)}")
            result[team_name] = {
                'campaigns': [],
                'campaigns_count': 0,
                'daily_budget': 0,
                'lifetime_budget': 0,
                'error': str(e)
            }
    
    # Add totals
    result['total'] = {
        'campaigns_count': total_campaigns,
        'daily_budget': total_daily_budget
    }
    
    return result


def format_budget_report(budget_data):
    """
    Format budget data into a readable report
    """
    report = []
    report.append("=" * 60)
    report.append("البادجت الشغال للحملات النشطة")
    report.append("=" * 60)
    report.append("")
    
    for team_name, data in budget_data.items():
        if team_name == 'total':
            continue
        
        report.append(f"تيم ({team_name})")
        report.append(f"  عدد الحملات النشطة: {data['campaigns_count']}")
        report.append(f"  البادجت اليومي: {data['daily_budget']:,.2f} ج")
        if data['lifetime_budget'] > 0:
            report.append(f"  البادجت الكلي: {data['lifetime_budget']:,.2f} ج")
        report.append("")
    
    if 'total' in budget_data:
        report.append("=" * 60)
        report.append("الإجمالي الكلي")
        report.append(f"  إجمالي عدد الحملات النشطة: {budget_data['total']['campaigns_count']}")
        report.append(f"  إجمالي البادجت اليومي: {budget_data['total']['daily_budget']:,.2f} ج")
        report.append("=" * 60)
    
    return "\n".join(report)
