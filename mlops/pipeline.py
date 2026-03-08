from models.recalibration import recalibrate
from models.promotion import promote_models

def weekly_mlops_cycle():
    recal = recalibrate()
    promo = promote_models([
        {"name":"ensemble_v1","sharpe":1.22},
        {"name":"ensemble_v2","sharpe":1.11},
    ])
    return {"recalibration": recal, "promotion": promo}
