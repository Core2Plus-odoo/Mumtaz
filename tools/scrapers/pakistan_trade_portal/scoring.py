def score_lead(record):
    score = 0

    # Pricing signal
    if record.price and "Ask" not in record.price:
        score += 10

    # MOQ signal
    if record.min_qty:
        score += 10

    # Sector weight (basic heuristic)
    high_value_sectors = ["Textile", "Leather", "Engineering", "Pharma"]
    if any(s.lower() in record.sector.lower() for s in high_value_sectors):
        score += 20

    # Product complexity
    if len(record.product_name.split()) > 3:
        score += 10

    # Base ERP fit
    erp_fit = min(score, 50)

    # Qualification buckets
    if score >= 40:
        qualification = "A"
    elif score >= 25:
        qualification = "B"
    else:
        qualification = "C"

    record.total_score = score
    record.erp_fit_score = erp_fit
    record.qualification = qualification

    # Suggested need mapping
    if qualification == "A":
        record.likely_need = "Full ERP Implementation"
        record.target_offer = "Odoo End-to-End"
    elif qualification == "B":
        record.likely_need = "Process Optimization"
        record.target_offer = "Health Check + Enhancements"
    else:
        record.likely_need = "Basic Digitization"
        record.target_offer = "Starter ERP"

    return record
