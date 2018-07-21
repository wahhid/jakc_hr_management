from openerp import models, fields, api, _
from openerp.exceptions import ValidationError, Warning



class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    shift_id = fields.Many2one('hr.shift')