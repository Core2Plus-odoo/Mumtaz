{
    'name': 'Faizy Work: Project task checklists',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Lets a FAIZY checklist attach to a standard Project task',
    'description': """
Bridge between Faizy Work and the standard Project app. Installs itself only when
both are present, so production is unaffected until Project is installed there
(which needs the founder's approval). Adds the checklist to the Project task form
and makes Project task a valid "attaches to" target for checklist templates.
""",
    'author': 'C2P Consultants',
    'license': 'LGPL-3',
    'depends': ['faizy_work', 'project'],
    'data': ['views/task_views.xml'],
    'auto_install': True,
    'installable': True,
    'application': False,
}
