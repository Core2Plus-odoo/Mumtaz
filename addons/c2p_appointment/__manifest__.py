{
    "name": "C2P Appointment Booking",
    "version": "19.0.1.0.0",
    "summary": "Public appointment booking with live availability, calendar sync and CRM capture",
    "description": """
Appointment booking for Odoo Community.

- Configurable appointment types (duration, staff, buffer, lead time)
- Availability computed from working hours minus existing calendar events
- Public booking page with date picker and live slot grid
- Creates a Calendar event and a CRM lead on booking
- Confirmation email with .ics calendar attachment
- Timezone aware
""",
    "category": "Services/Appointment",
    "author": "C2P Group",
    "website": "https://core2plus.com",
    "depends": ["base", "calendar", "resource", "website", "crm", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/appointment_data.xml",
        "data/mail_template.xml",
        "views/appointment_views.xml",
        "views/website_templates.xml",
        "views/appointment_menus.xml",
    ],
    "application": True,
    "installable": True,
    "license": "LGPL-3",
}
