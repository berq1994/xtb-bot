from typing import Dict, List


def build_decision_overlay(briefing_items: List[Dict], alerts: List[Dict], evaluation: Dict) -> Dict:
    high_count = sum(1 for x in briefing_items if x.get('priority') == 'HIGH') + sum(1 for x in alerts if x.get('priority') == 'HIGH')
    medium_count = sum(1 for x in briefing_items if x.get('priority') == 'MEDIUM') + sum(1 for x in alerts if x.get('priority') == 'MEDIUM')
    rejected = evaluation.get('rejected_count', 0)

    if high_count >= 2:
        recommended_mode = 'DEFENSIVE'
        max_new_positions = 1
        portfolio_note = 'Zvýšené event risk. Nové vstupy jen selektivně a s menší velikostí.'
    elif medium_count >= 2:
        recommended_mode = 'SELECTIVE'
        max_new_positions = 2
        portfolio_note = 'Několik témat je aktivních. Preferovat jen čisté setupy s potvrzením.'
    else:
        recommended_mode = 'NORMAL'
        max_new_positions = 3
        portfolio_note = 'Tok zpráv je zvládnutelný. Standardní selekce bez eskalace rizika.'

    if rejected >= 2:
        recommended_mode = 'CAUTIOUS'
        max_new_positions = min(max_new_positions, 1)
        portfolio_note = 'Část alertů byla vyřazena kritikem. Požaduj silnější potvrzení price action.'

    return {
        'recommended_mode': recommended_mode,
        'max_new_positions': max_new_positions,
        'portfolio_note': portfolio_note,
    }
