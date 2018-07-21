from openerp import models, api, fields, _
from openerp.exceptions import ValidationError, Warning
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):

    _name = 'hr.attendance'
    _inherit = 'hr.attendance'

    @api.one
    def trans_process(self):
        hr_schedule_detail_obj = self.env['hr.schedule.detail']
        hr_schedule_alert_rule_obj = self.env['hr.schedule.alert.rule']
        hr_schedule_alert_obj  = self.env['hr.schedule.alert']
        for att in self:
            _logger.info("Check Rule By Punch")
            if att.schedule_detail_id:
                schedule_detail_id = att.schedule_detail_id
            else:
                #Get Day
                att.day = datetime.strptime(self.name,'%Y-%m-%d %H:%M:%S').date()
                _logger.info(att.day)
                #Get Schedule Detail
                args = [('day','=', att.day),('employee_id','=', att.employee_id.id)]
                schedule_detail_ids = hr_schedule_detail_obj.search(args)
                if schedule_detail_ids:
                    schedule_detail_id = schedule_detail_ids[0].id
                    att.schedule_detail_id = schedule_detail_id

            if att.name < schedule_detail_id.date_start:
                schedule_detail_id.actual_date_start = att.name
            if att.name > schedule_detail_id.date_end:
                schedule_detail_id.actual_date_end = att.name

            rules = hr_schedule_alert_rule_obj.check_rule_by_punch(att)
            att.alert_ids.unlink()
            for rule in rules:
                vals = {}
                vals.update({'name':datetime.now()})
                vals.update({'rule_id':rule['rule_id']})
                vals.update({'attendance_id': att.id})
                vals.update({'sched_detail_id':schedule_detail_id.id})
                vals.update({'employee_id':att.employee_id.id})
                hr_schedule_alert_obj.create(vals)
                _logger.info("Create Alert Rule")

            if len(rules) > 0:
                att.state = 'exception'

    day = fields.Date('Date', readonly=True)
    schedule_detail_id = fields.Many2one('hr.schedule.detail','Schedule', readonly=True)
    alert_ids = fields.One2many('hr.schedule.alert', 'attendance_id', 'Exceptions', readonly=True)
    state = fields.Selection([('open','Open'),
                              ('exception','Exception'),
                              ('locked','Locked'),
                              ('lockede','Lock with Exception')],'Status',default='open')

    @api.model
    def create(self, vals):
        res = super(HrAttendance, self).create(vals)
        res.trans_process()
        return res

    @api.one
    def _altern_si_so(self):
        return True

    _constraints = [(_altern_si_so, 'Error ! Sign in (resp. Sign out) must follow Sign out (resp. Sign in)', ['action'])]