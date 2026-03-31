from contact_detection import extract_contacts, detect_exporter_signals


def enrich_company(company: dict) -> dict:
    text_blob = " ".join([
        company.get('company_name',''),
        " ".join(company.get('sample_products', [])),
        company.get('city',''),
        company.get('sector','')
    ])

    contacts = extract_contacts(text_blob)
    exporter = detect_exporter_signals(text_blob)

    company.update({
        'emails': contacts['emails'],
        'phones': contacts['phones'],
        'has_contact': contacts['has_contact'],
        'exporter_signal_score': exporter['exporter_signal_score'],
        'export_status': exporter['export_status'],
        'export_keywords': exporter['exporter_keywords_found'],
        'certifications': exporter['certifications_found'],
    })

    # Upgrade qualification based on exporter + contacts
    if company['exporter_signal_score'] > 40 and company['has_contact']:
        company['qualification'] = 'A'
    elif company['exporter_signal_score'] > 15:
        company['qualification'] = 'B'

    return company
