{
    'name': 'Mumtaz Jewellery: AI agents',
    'version': '19.0.1.0.0',
    'summary': 'Layla and Zayan: prepared trays, drafted follow-ups, the morning brief, an approvals inbox',
    'description': """
Plan v3, sections 12-13 and wireframe 29. Two agents, bounded:

* **Layla** (client & retail, ceiling C): prepares a Private Tray through the
  same deterministic ranking staff use, and drafts a follow-up a person
  reviews, approves and sends herself. Never sends.
* **Zayan** (coordinator, ceiling B): the morning brief and the decision
  queue, every figure read from the engine with its source and time; the
  command bar routes a request to the right tool.

The rules that hold whatever the model says:

* Numbers are read, never produced. Prices come from the pricing engine at the
  approved rate; the model may quote them. A model sentence that carries a
  number the tools did not supply is discarded and the local wording used.
* A Private or Royal client never enters a model request. Drafts for them
  take the local, deterministic path or are unavailable.
* Every run is logged (who, which tool, which level, model or local, tokens,
  outcome). Refused calls are logged too: the refusal is the control working.
* Approval binds to the exact payload: edit the draft and it needs review
  again. Approving a follow-up marks it ready for a person to send; nothing
  here sends a message.
* The owner can pause the tenant's AI; the counter keeps working.

The model provider is optional. With no key configured every capability
still works on its local path, so the product never depends on a model to
sell.
    """,
    'author': 'Mumtaz Digital',
    'license': 'LGPL-3',
    'category': 'Sales/CRM',
    'depends': ['mumtaz_jewellery_crm', 'mumtaz_jewellery_owner'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ai_data.xml',
    ],
    'installable': True,
    'application': False,
}
