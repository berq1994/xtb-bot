from typing import Dict, List


def review_alerts(alerts: List[Dict]) -> Dict:
    reviews = []
    approved_count = 0
    for item in alerts:
        score = float(item.get('confidence', 0.0))
        reasons = []
        if not item.get('tickers'):
            score -= 0.15
            reasons.append('Chybí tickery')
        if item.get('priority') == 'LOW':
            score -= 0.10
            reasons.append('Low priority')
        if item.get('status') == 'NO TRADE':
            score -= 0.05
            reasons.append('Status no-trade')
        if 'risk' not in item.get('risk_note', '').lower() and 'riziko' not in item.get('risk_note', '').lower():
            score -= 0.05
            reasons.append('Slabá risk poznámka')
        final_score = round(max(0.0, min(1.0, score)), 2)
        approved = final_score >= 0.68
        if approved:
            approved_count += 1
        reviews.append({
            'category': item.get('category'),
            'title': item.get('title'),
            'critic_score': final_score,
            'approved': approved,
            'reasons': reasons or ['OK'],
        })
    return {
        'approved_count': approved_count,
        'rejected_count': len(alerts) - approved_count,
        'reviews': reviews,
    }
