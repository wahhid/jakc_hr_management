import time
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pytz import timezone, utc
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError,  Warning
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT as OE_DTFORMAT
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as OE_DFORMAT

import logging
_logger = logging.getLogger(__name__)

DAYOFWEEK_SELECTION = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]

AVAILABLE_SCHEDULE_STATE = [
    ('draft', 'Draft'),
    ('validate', 'Confirmed'),
    ('locked', 'Locked'),
    ('unlocked', 'Unlocked'),
]


class WeekDays(models.Model):

    _name = 'hr.schedule.weekday'
    _description = 'Days of the Week'

    name = fields.Char('Name',size=64,required=True,)
    sequence = fields.Integer('Sequence',required=True,)


class HrSchedule(models.Model):
    _name = 'hr.schedule'

    @api.multi
    def float_time_convert(self, float_val):
        factor = float_val < 0 and -1 or 1
        val = abs(float_val)
        return (factor * int(math.floor(val)), int(round((val % 1) * 60)))

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        self.department_id = self.employee_id.department_id

    @api.onchange('date_start')
    def onchange_employee_date_start(self):
        dStart = False
        edata = False
        if self.employee_id:
            if self.date_start:
                dStart = datetime.strptime(self.date_start, '%Y-%m-%d').date()
                # The schedule must start on a Monday
                if dStart.weekday() != 0:
                    self.date_start = False
                    self.date_end = False
                else:
                    dEnd = dStart + relativedelta(days=+6)
                    self.date_end = dEnd
                self.name = self.employee_id.name + ': ' + dStart.strftime('%Y-%m-%d') + ' Wk ' + str(dStart.isocalendar()[1])

            if self.employee_id.contract_id:
                self.contract_id = self.employee_id.contract_id

        else:
            self.date_start = False
            self.date_end = False

    @api.one
    def create_details(self):
        leave_obj = self.env['hr.holidays']
        for schedule in self:
            if schedule.template_id:
                leaves = []
                leaves_args = [('employee_id', '=', schedule.employee_id.id),
                              ('date_from', '<=', schedule.date_end),
                              ('date_to', '>=', schedule.date_start),
                              ('state', 'in', ['draft', 'validate', 'validate1'])]
                leaves_ids = leave_obj.search(leaves_args)

                for lv in leaves_ids:
                    utcdtFrom = utc.localize(datetime.strptime(lv.date_from, OE_DTFORMAT), is_dst=False)
                    utcdtTo = utc.localize(datetime.strptime(lv.date_to, OE_DTFORMAT), is_dst=False)
                    leaves.append((utcdtFrom, utcdtTo))

                user = self.env.user
                local_tz = timezone(user.tz)
                dCount = datetime.strptime(schedule.date_start, '%Y-%m-%d').date()
                dCountEnd = datetime.strptime(schedule.date_end, '%Y-%m-%d').date()
                dWeekStart = dCount
                dSchedStart = dCount
                while dCount <= dCountEnd:
                    prevutcdtStart = False
                    prevDayofWeek = False
                    for worktime in schedule.template_id.attendance_ids:

                        hour, minute = self.float_time_convert(worktime.hour_from)
                        toHour, toMin = self.float_time_convert(worktime.hour_to)


                        # TODO - Someone affected by DST should fix this
                        #
                        dtStart = datetime.strptime(dWeekStart.strftime('%Y-%m-%d') + ' ' + str(hour) + ':' + str(minute) + ':00','%Y-%m-%d %H:%M:%S')
                        locldtStart = local_tz.localize(dtStart, is_dst=False)
                        utcdtStart = locldtStart.astimezone(utc)
                        if worktime.dayofweek != 0:
                            utcdtStart = utcdtStart + relativedelta(days=+int(worktime.dayofweek))
                        dDay = utcdtStart.astimezone(local_tz).date()

                        # If this worktime is a continuation (i.e - after lunch)
                        # set the start time based on the difference from the
                        # previous record
                        #
                        if prevDayofWeek and prevDayofWeek == worktime.dayofweek:
                            prevHour = prevutcdtStart.strftime('%H')
                            prevMin = prevutcdtStart.strftime('%M')
                            curHour = utcdtStart.strftime('%H')
                            curMin = utcdtStart.strftime('%M')
                            delta_seconds = (datetime.strptime(curHour + ':' + curMin, '%H:%M') - datetime.strptime(prevHour + ':' + prevMin,'%H:%M')).seconds
                            utcdtStart = prevutcdtStart + timedelta(seconds=+delta_seconds)
                            dDay = prevutcdtStart.astimezone(local_tz).date()

                        delta_seconds = (datetime.strptime(str(toHour) + ':' + str(toMin),'%H:%M')- datetime.strptime(str(hour) + ':' + str(minute),'%H:%M')).seconds
                        utcdtEnd = utcdtStart + timedelta(seconds=+delta_seconds)

                        # Leave empty holes where there are leaves
                        #
                        _skip = False
                        for utcdtFrom, utcdtTo in leaves:
                            if utcdtFrom <= utcdtStart and utcdtTo >= utcdtEnd:
                                _skip = True
                                break
                            elif utcdtStart < utcdtFrom <= utcdtEnd:
                                if utcdtTo == utcdtEnd:
                                    _skip = True
                                else:
                                    utcdtEnd = utcdtFrom + timedelta(seconds=-1)
                                break
                            elif utcdtStart <= utcdtTo < utcdtEnd:
                                if utcdtTo == utcdtEnd:
                                    _skip = True
                                else:
                                    utcdtStart = utcdtTo + timedelta(seconds=+1)
                                break
                        if not _skip:
                            val = {
                                'name': schedule.name,
                                'dayofweek': worktime.dayofweek,
                                'day': dDay,
                                'date_start': utcdtStart.strftime('%Y-%m-%d %H:%M:%S'),
                                'date_end': utcdtEnd.strftime('%Y-%m-%d %H:%M:%S'),
                                'schedule_id': schedule.id,
                            }
                            self.write({'detail_ids': [(0, 0, val)]})

                        prevDayofWeek = worktime.dayofweek
                        prevutcdtStart = utcdtStart

                    dCount = dWeekStart + relativedelta(weeks=+1)
                    dWeekStart = dCount
        return True

    @api.one
    def trans_validate(self):
        for schedule in self:
            detail_ids = schedule.detail_ids
            detail_ids.write({'state':'validate'})
            schedule.state = 'validate'

    name = fields.Char('Description', size=64, required=True, reaodnly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, readonly=True,states = {'draft': [('readonly', False)]})
    template_id = fields.Many2one('resource.calendar', 'Schedule Template',readonly=True, states={'draft': [('readonly', False)]},)
    detail_ids = fields.One2many('hr.schedule.detail','schedule_id','Schedule Detail',readonly=True,states={'draft': [('readonly', False)]},)
    state = fields.Selection(AVAILABLE_SCHEDULE_STATE,'State',required=True,readonly=True,default='draft')
    date_start =  fields.Date('Start Date',required=True,readonly=True,states={'draft': [('readonly', False)]})
    date_end = fields.Date('End Date',required=True,readonly=True,states={'draft': [('readonly', False)]})
    department_id = fields.Many2one('hr.department','Department', relation='employee_id.department_id', readonly=True, store=True)

    @api.model
    def create(self, vals):
        res = super(HrSchedule, self).create(vals)
        res.create_details()
        return res

    def _schedule_date(self):
        for shd in self:
            self.env.cr.execute("""\
                        SELECT id
                        FROM hr_schedule
                        WHERE (date_start <= %s and %s <= date_end)
                          AND employee_id=%s
                          AND id <> %s""", (shd.date_end, shd.date_start, shd.employee_id.id, shd.id))
            if self.env.cr.fetchall():
                return False
        return True

    def _rec_message(self):
        return _('You cannot have schedules that overlap!')

    _constraints = [
        (_schedule_date, _rec_message, ['date_start', 'date_end']),
    ]


class HrScheduleDetail(models.Model):
    _name = "hr.schedule.detail"
    _description = "Schedule Detail"
    _order = 'schedule_id, date_start, dayofweek'

    name = fields.Char(
        "Name",
        size=64,
        required=True,
    )
    dayofweek = fields.Selection(
        DAYOFWEEK_SELECTION,
        'Day of Week',
        required=True,
        index=True,
    )
    date_start = fields.Datetime(
        'Start Date and Time',
        required=True,
    )
    date_end = fields.Datetime(
        'End Date and Time',
        required=True,
    )
    day = fields.Date(
        'Day',
        required=True,
        index=True,
    )
    schedule_id = fields.Many2one(
        'hr.schedule',
        'Schedule',
        ondelete='cascade',
        required=True,
    )
    department_id = fields.Many2one('hr.department', 'Department', related='schedule_id.department_id', store=True)

    employee_id = fields.Many2one('hr.employee','Employee', related='schedule_id.employee_id', store=True, index=True)

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('validate', 'Confirmed'),
            ('leave','Leaves'),
            ('public','Public'),
            ('locked', 'Locked'),
            ('unlocked', 'Unlocked'),
        ],
        'State',
        required=True,
        readonly=True,
        default='draft',
    )


class HrScheduleRequest(models.Model):

    _name = 'hr.schedule.request'
    _description = 'Change Request'

    _inherit = ['mail.thread']

    employee_id = fields.Many2one(
            'hr.employee',
            'Employee',
            required=True,
        )
    date = fields.Date(
            'Date',
            required=True,
        )
    type = fields.Selection(
            [
                ('missedp', 'Missed Punch'),
                ('adjp', 'Punch Adjustment'),
                ('absence', 'Absence'),
                ('schedadj', 'Schedule Adjustment'),
                ('other', 'Other'),
            ],
            'Type',
            required=True,
        )
    message = fields.Text(
            'Message',
        )
    state = fields.Selection(
            [
                ('pending', 'Pending'),
                ('auth', 'Authorized'),
                ('denied', 'Denied'),
                ('cancel', 'Cancelled'),
            ],
            'State',
            required=True,
            readonly=True,
            default='pending',
        )


class HrScheduleAlertRule(models.Model):

    _name = 'hr.schedule.alert.rule'
    _description = 'Scheduling/Attendance Exception Rule'

    name = fields.Char('Name', size=64, required=True)
    code = fields.Char('Code', size=20, required=True)
    severity = fields.Selection([
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ], 'Severity', required=True, default='low')
    grace_period = fields.Integer(
            'Grace Period',
            help='In the case of early or late rules, the amount of time '
                 'before/after the scheduled time that the rule will trigger.'
        )
    window = fields.Integer('Window of Activation')
    active = fields.Boolean('Active', default=True)


    def check_rule_by_punch(self, att):
        res = []
        rules = self.search([('active','=',True)])
        _logger.info(rules)
        for rule in rules:
            _logger.info(rule.name)
            if rule.code == 'MISSPUNCHIN':
                _logger.info('CHECK MISSPUNCHIN')
                if not att.check_in:
                    _logger.info('MISSPUNCHIN')
                    res.append({'attendance_id': att.id, 'rule_id': rule.id})

            elif rule.code == 'MISSPUNCHOUT':
                _logger.info('CHECK MISSPUNCHOUT')
                if not att.check_out:
                    _logger.info('MISSPUNCHOUT')
                    res.append({'attendance_id': att.id, 'rule_id': rule.id})


            elif rule.code == 'UNSCHEDATT':
                _logger.info('CHECK UNSCHEDATT')
                if not att.schedule_detail_id:
                    _logger.info('UNSCHEDATT')
                    res.append({'attendance_id': att.id, 'rule_id': rule.id})


            elif rule.code == 'LVEARLY':
                _logger.info('CHECK LVEARLY')
                schedule_detail_id = att.schedule_detail_id
                if schedule_detail_id.date_end > att.check_out:
                    _logger.info('LVEARLY')
                    res.append({'attendance_id': att.id, 'rule_id': rule.id})

            elif rule.code == 'INLATE':
                _logger.info('CHECK INLATE')
                schedule_detail_id = att.schedule_detail_id
                if schedule_detail_id.date_start < att.check_in:
                    _logger.info('INLATE')
                    res.append({'attendance_id': att.id, 'rule_id': rule.id})
        return res


class HrScheduleAlert(models.Model):

    _name = 'hr.schedule.alert'
    _description = 'Attendance Exception'
    _inherit = ['mail.thread', 'resource.calendar']

    def _get_employee_id(self):
        res = {}
        for alrt in self:
            if alrt.punch_id:
                res[alrt.id] = alrt.punch_id.employee_id.id
            elif alrt.sched_detail_id:
                res[alrt.id] = alrt.sched_detail_id.schedule_id.employee_id.id
            else:
                res[alrt.id] = False
        return res

    name = fields.Datetime(
            'Date and Time',
            required=True,
            readonly=True,
    )
    rule_id = fields.Many2one(
            'hr.schedule.alert.rule',
            'Alert Rule',
            required=True,
            readonly=True,
    )
    punch_id = fields.Many2one(
            'hr.attendance',
            'Triggering Punch',
            readonly=True,
        )
    sched_detail_id = fields.Many2one(
            'hr.schedule.detail',
            'Schedule Detail',
            readonly=True,
        )
    employee_id = fields.Many2one(
            comodel_name='hr.employee',
            compute='_get_employee_id',
            store=True,
            string='Employee',
            readonly=True,
        )
    department_id = fields.Many2one('hr.department','Department',related='employee_id.department_id',readonly=True)
    severity = fields.Selection([
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],'Severity', related='rule_id.severity',store=True,readonly=True)
    state = fields.Selection(
            [
                ('unresolved', 'Unresolved'),
                ('resolved', 'Resolved'),
            ],
            'State',
            readonly=True,
            default='unresolved'
        )


    def _rec_message(self):
        return _('Duplicate Record!')

    _sql_constraints = [
        ('all_unique', 'UNIQUE(punch_id,sched_detail_id,name,rule_id)',
         _rec_message),
    ]

    _track = {
        'state': {
            'hr_schedule.mt_alert_resolved': (
                lambda self, r, u, obj, ctx=None: obj['state'] == 'resolved'
            ),
            'hr_schedule.mt_alert_unresolved': (
                lambda self, r, u, obj, ctx=None: obj['state'] == 'unresolved'
            ),
        },
    }


class HrAttendance(models.Model):

    _name = 'hr.attendance'
    _inherit = 'hr.attendance'


    @api.one
    def trans_process(self):
        hr_schedule_alert_rule_obj = self.env['hr.schedule.alert.rule']
        hr_schedule_alert_obj  = self.env['hr.schedule.alert']
        for att in self:
            _logger.info("Check Rule By Punch")
            rules = hr_schedule_alert_rule_obj.check_rule_by_punch(att)
            att.alert_ids.unlink()
            for rule in rules:
                #Create Alert
                vals = {}
                vals.update({'name':datetime.now()})
                vals.update({'rule_id':rule['rule_id']})
                vals.update({'punch_id':rule['attendance_id']})
                vals.update({'sched_detail_id':att.schedule_detail_id.id})
                vals.update({'employee_id': att.employee_id.id})
                hr_schedule_alert_obj.create(vals)

            if len(rules) > 0:
                self.state = 'exception'

    day = fields.Date('Date', readonly=True)
    schedule_detail_id = fields.Many2one('hr.schedule.detail','Schedule', readonly=True)
    punch_ids = fields.One2many('hr.punch', 'attendance_id', 'Punchs', readonly=True)
    alert_ids = fields.One2many('hr.schedule.alert', 'punch_id', 'Exceptions', readonly=True)
    state = fields.Selection([('open','Open'),('exception','Exception'),('locked','Locked'),('lockede','Lock with Exception')],'Status',default='open')


class HrPunch(models.Model):
    _name = 'hr.punch'

    @api.one
    def trans_process(self):
        for punch in self:
            employee_id = punch.employee_id
            punch_date_time = punch.punch_date_time
            punch_date = datetime.strptime(punch_date_time, '%Y-%m-%d %H:%M:%S').date()
            str_punch_date = punch_date.strftime('%Y-%m-%d')
            _logger.info(str_punch_date)
            _logger.info(employee_id)
            schedule_detail_obj = self.env['hr.schedule.detail']
            schedule_detail_args = [('day', '=', str_punch_date), ('employee_id', '=', employee_id.id)]
            schedule_detail_ids = schedule_detail_obj.search(schedule_detail_args)
            _logger.info(schedule_detail_ids)

            if len(schedule_detail_ids) > 0:
                schedule_detail_id = schedule_detail_ids[0]
                punch.schedule_id = schedule_detail_id.id
                check_in_status = False
                check_out_status = False
                if schedule_detail_id.date_start > punch_date_time:
                    check_in_status = True
                elif datetime.strptime(schedule_detail_id.date_start, '%Y-%m-%d %H:%M:%S')  + timedelta(hours=4) > datetime.strptime(punch_date_time,  '%Y-%m-%d %H:%M:%S') :
                    check_in_status = True
                elif schedule_detail_id.date_end < punch_date_time:
                    check_out_status = True
                elif datetime.strptime(schedule_detail_id.date_end, '%Y-%m-%d %H:%M:%S') + timedelta(hours=-4) < datetime.strptime(punch_date_time,  '%Y-%m-%d %H:%M:%S'):
                    check_out_status = True

                hr_attendance_obj = self.env['hr.attendance']
                hr_attendance_args = [('day', '=', punch_date)]
                hr_attendance_ids = hr_attendance_obj.search(hr_attendance_args)
                if not hr_attendance_ids:
                    # Create Hr Attendance
                    attendance_vals = {}
                    attendance_vals.update({'day': punch_date})
                    attendance_vals.update({'employee_id': employee_id.id})
                    if check_in_status:
                        attendance_vals.update({'check_in': punch_date_time})
                    if check_out_status:
                        attendance_vals.update({'check_out': punch_date_time})
                    hr_attendance_id = hr_attendance_obj.create(attendance_vals)
                    hr_attendance_id.schedule_detail_id = schedule_detail_id.id

                else:
                    #Update Hr Attendance
                    hr_attendance_id = hr_attendance_ids[0]
                    attendance_vals = {}
                    if check_in_status:
                        if hr_attendance_id.check_in > punch_date_time:
                            attendance_vals.update({'check_in': punch_date_time})
                    if check_out_status:
                        if hr_attendance_id.check_out < punch_date_time:
                            attendance_vals.update({'check_out': punch_date_time})
                    hr_attendance_id.write(attendance_vals)
                    hr_attendance_id.schedule_detail_id = schedule_detail_id.id

                self.schedule_detail_id = schedule_detail_id.id
                punch.state = 'locked'

    employee_id = fields.Many2one('hr.employee','Employee', readonly=False)
    punch_date_time = fields.Datetime('Punch Date', readonly=False)
    schedule_detail_id = fields.Many2one('hr.schedule.detail','Schedule Detail', reaodnly=True)
    attendance_id = fields.Many2one('hr.attendance', 'Attendance', readonly=True)
    state = fields.Selection(AVAILABLE_SCHEDULE_STATE, 'Status', default='draft', readonly=True)


class HrHolidays(models.Model):

    _inherit = 'hr.holidays'

    def holidays_validate(self):

        res = super(HrHolidays, self).holidays_validate()

        unlink_ids = []

        det_obj = self.env['hr.schedule.detail']
        for leave in self:
            if leave.type != 'remove':
                continue

            det_ids = det_obj.search(
                     [(
                    'schedule_id.employee_id', '=', leave.employee_id.id),
                    ('date_start', '<=', leave.date_to),
                    ('date_end', '>=', leave.date_from)],
                order='date_start')

            for detail in det_ids:

                # Remove schedule details completely covered by leave
                if (leave.date_from <= detail.date_start
                        and leave.date_to >= detail.date_end
                        and detail.id not in unlink_ids):
                    unlink_ids.append(detail.id)

                # Partial day on first day of leave
                elif detail.date_start < leave.date_from <= detail.date_end:
                    dtLv = datetime.strptime(leave.date_from, OE_DTFORMAT)
                    if leave.date_from == detail.date_end:
                        if detail.id not in unlink_ids:
                            unlink_ids.append(detail.id)
                        else:
                            dtEnd = dtLv + timedelta(seconds=-1)
                            detail.write({'date_end': dtEnd.strftime(OE_DTFORMAT)})

                # Partial day on last day of leave
                elif detail.date_end > leave.date_to >= detail.date_start:
                    dtLv = datetime.strptime(leave.date_to, OE_DTFORMAT)
                    if leave.date_to != detail.date_start:
                        dtStart = dtLv + timedelta(seconds=+1)
                        detail.write({'date_start': dtStart.strftime(OE_DTFORMAT)})

        det_obj.unlink(unlink_ids)

        return res

    def holidays_refuse(self):

        res = super(HrHolidays, self).holidays_refuse()

        sched_obj = self.env['hr.schedule']
        for leave in self:
            if leave.type != 'remove':
                continue

            dLvFrom = datetime.strptime(leave.date_from, OE_DTFORMAT).date()
            dLvTo = datetime.strptime(leave.date_to, OE_DTFORMAT).date()
            sched_ids = sched_obj.search([('employee_id', '=', leave.employee_id.id),
                          ('date_start', '<=', dLvTo.strftime(OE_DFORMAT)),
                          ('date_end', '>=', dLvFrom.strftime(OE_DFORMAT))])

            # Re-create affected schedules from scratch
            for sched_id in sched_ids:
                sched_obj.delete_details(sched_id.id)
                sched_obj.create_details(sched_id.id)

        return res

"""
class HrTerm(models.Model):

    _inherit = 'hr.employee.termination'

    def create(self):

        res = super(HrTerm, self).create()

        det_obj = self.env['hr.schedule.detail']
        term = self
        user = self.env.user
        if user and user.tz:
            local_tz = timezone(user.tz)
        else:
            local_tz = timezone('Asia/Jakarta')
        dt = datetime.strptime(term.name + ' 00:00:00', OE_DTFORMAT)
        utcdt = (local_tz.localize(dt, is_dst=False)).astimezone(utc)
        det_ids = det_obj.search(
                    [('schedule_id.employee_id', '=', term.employee_id.id),
                      ('date_start', '>=', utcdt.strftime(OE_DTFORMAT))],
                    order='date_start')
        det_ids.unlink()
        return res

    def _restore_schedule(self):

        sched_obj = self.pool.get('hr.schedule')
        for term in self:
            d = datetime.strptime(term.name, OE_DFORMAT).date()
            sched_ids = sched_obj.search(
                         [('employee_id', '=', term.employee_id.id),
                          ('date_start', '<=', d.strftime(
                              OE_DFORMAT)),
                          ('date_end', '>=', d.strftime(OE_DFORMAT))])

            # Re-create affected schedules from scratch
            for sched_id in sched_ids:
                sched_obj.delete_details(sched_id.id)
                sched_obj.create_details(sched_id.id)

        return

    def state_cancel(self):
        self._restore_schedule()
        res = super(HrTerm, self).state_cancel()
        return res

    def unlink(self):
        self._restore_schedule()
        res = super(HrTerm, self).unlink()
        return res
"""