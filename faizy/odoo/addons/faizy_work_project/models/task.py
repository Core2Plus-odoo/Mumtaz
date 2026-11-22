from odoo import fields, models


class ChecklistTemplate(models.Model):
    _inherit = 'faizy.checklist.template'

    res_model = fields.Selection(selection_add=[('project.task', 'Project task')],
                                 ondelete={'project.task': 'set default'})


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'faizy.checklist.mixin']
