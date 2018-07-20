# -*- coding: utf-8 -*-

import time
from datetime import datetime

from openerp import models, fields, api, _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import except_orm, Warning, RedirectWarning

Datetime_FORMAT = '%Y-%m-%d'

class hr_overtime_multiple(models.Model):
    _name = 'hr.overtime.multiple'
    _description = 'Employee Overtime Multiple'
    
    _rec_name = 'date_from'
    
    @api.multi
    def unlink(self):
        for request in self:
            if request.state not in ('draft', 'cancel'):
                raise Warning(_('You cannot delete an multiple overtime request which is not draft or cancelled.'))
        return super(hr_overtime_multiple, self).unlink()
    
    @api.model
    def _employee_get(self):
        ids = self.env['hr.employee'].search([('user_id', '=', self._uid)], limit=1)
        if ids:
            return ids
    
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    name = fields.Char(string='Description', required=False, states={'validate':[('readonly', True)]})
    number_of_hours = fields.Float(string='Number Of Hours', states={'validate':[('readonly', True)]}, store=True)
    include_payroll = fields.Boolean(string='Include In Payroll', states={'validate':[('readonly', True)]}, help='Tick if you want to include this overtime in employee payroll', default=True)
    state = fields.Selection(selection=[('draft', 'New'), ('confirm', 'Waiting First Approval'),('approve_by_hr', 'Waiting Department Approval'), ('refuse', 'Refused'),
                                        ('validate', 'Done'), ('cancel', 'Cancelled')],
                                string='Status', readonly=True, default='draft', track_visibility='onchange')
    user_id = fields.Many2one('res.users' ,string='User', default=lambda self: self.env.user)
    date_from = fields.Datetime(string='Start Date', readonly=False, states={'validate':[('readonly', True)]}, default=fields.datetime.now()) 
    date_to = fields.Datetime(string='End Date', readonly=False, states={'validate':[('readonly', True)]})
    approve_date = fields.Date(string='Department Approved Date', readonly=True, copy=False)
    hr_approve_date = fields.Date(string='Approved Date', readonly=True, copy=False)
    employee_ids = fields.Many2many('hr.employee', 'employee_overtime_multiple_rel','employee_id','overtime_id' ,string="Select Employees", required=True,states={'validate':[('readonly', True)]})
    manager_id = fields.Many2one('hr.employee', 'Manager', readonly=False, states={'validate':[('readonly', True)]}, help='This area is automatically filled by the user who will approve the request', copy=False)
    notes = fields.Text(string='Notes',)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    category_id = fields.Many2one('hr.employee.category', string="Category", readonly=False, states={'validate':[('readonly', True)]}, help='Category of Employee')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False, states={'validate':[('readonly', True)]},default=lambda self: self.env['res.company']._company_default_get('hr.overtime.multiple'))
    approve_hr_manager_id = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    approve_dept_manager_id = fields.Many2one('res.users', string='Department Manager', readonly=True, copy=False)
    department_manager_id = fields.Many2one('hr.employee', string='Department Manager(RR)')
    
    @api.onchange('department_id')
    def onchange_department(self):
        self.department_manager_id = self.department_id.manager_id and self.department_id.manager_id.id or False
    
    @api.onchange('date_from')
    def onchange_start_date(self):
        if self.date_to and self.date_from:
            date_start = datetime.strptime(self.date_from, "%Y-%m-%d %H:%M:%S")
            date_end = datetime.strptime(self.date_to, "%Y-%m-%d %H:%M:%S")
            diff_hours = date_end - date_start
            self.number_of_hours = (diff_hours.seconds / 3600.00) + (diff_hours.days * 24.00)
        else:
            self.number_of_hours = 0.0
    
    @api.onchange('date_to')
    def onchange_end_date(self):
        if self.date_to and self.date_from:
            date_start = datetime.strptime(self.date_from, "%Y-%m-%d %H:%M:%S")
            date_end = datetime.strptime(self.date_to, "%Y-%m-%d %H:%M:%S")
            diff_hours = date_end - date_start
            self.number_of_hours = (diff_hours.seconds / 3600.00) + (diff_hours.days * 24.00)
        else:
            self.number_of_hours = 0.0
    
    @api.multi
    def set_to_draft(self):
        self.write({
            'state': 'draft',
            'approve_date': False,
            'hr_approve_date': False,
            'approve_hr_manager_id': False,
            'approve_dept_manager_id' : False
        })
        return True
    
    @api.multi
    def ot_refuse(self):
        obj_emp = self.env['hr.employee']
        ids2 = obj_emp.search([('user_id', '=', self._uid)], limit=1)
        manager = ids2 or False
        self.write({'state': 'refuse', 'manager_id':  manager and manager.id or False})
        return True
    
    @api.multi
    def department_approve(self):
        obj_emp = self.env['hr.employee']
        ids2 = obj_emp.search([('user_id', '=', self._uid)], limit=1)
        manager = ids2 or False
        
        self.write({'state': 'validate', 'approve_dept_manager_id' : self.env.user.id, 'approve_date': time.strftime('%Y-%m-%d'),})
        if self.employee_ids:
            for employee in self.employee_ids:
                overtime_vals=  {
                    'date_from' :  self.date_from,
                    'date_to' : self.date_to,
                    'approve_date' :  self.approve_date,
                    'hr_approve_date' :  self.hr_approve_date,
                    'manager_id' : self.manager_id and self.manager_id.id or False,
                    'notes' : self.notes,
                    'category_id': self.category_id.id,
                    'company_id': self.company_id.id,
                    'approve_hr_manager_id': self.approve_hr_manager_id.id,
                    'approve_dept_manager_id' : self.approve_dept_manager_id.id,
                    'state' : 'validate',
                    'include_payroll': self.include_payroll,
                    'number_of_hours' : self.number_of_hours,
                    'multiple_overtime_id' : self.id,
                    'employee_id': employee.id,
                    'name' : employee.name
                }
                overtime_id = self.env['hr.overtime'].create(overtime_vals)
        return True

    @api.multi
    def ot_cancel(self):
        self.write({'state': 'cancel'})
        return True
    
    @api.multi
    def ot_confirm(self):
        return self.write({'state':'confirm'})

    @api.multi
    def hr_approval(self):
        return self.write({'state':'approve_by_hr', 'approve_hr_manager_id': self.env.user.id, 'hr_approve_date': time.strftime('%Y-%m-%d')})

