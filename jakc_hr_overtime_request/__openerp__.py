# -*- coding: utf-8 -*-
# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.
{
    'name' : 'HR Overtime Request and Payroll',
    'license': 'Other proprietary',
    'version': '1.0',
    'author': 'Probuse Consulting Service Pvt. Ltd.',
    'category' : 'Human Resources',
    'price': 50.0,
    'currency': 'EUR',
    'live_test_url': 'https://youtu.be/kFN2ILIVw20',
    'images': ['static/description/img143.jpg'],
    'website': 'https://www.probuse.com',
    'description': ''' 
This module add below features which can be used to manage overtime requests:
  * Overtime Requests: This will be request by employee.
  * Multiple Overtime Requests: This request can be created by HR Manager or Department Manager on behalf of multiple employees together.
  * Integrate Overtime Requests in Employee Payslips: This will show payslip lines in payslip of employee.

Note: This module add new group called "Department Manager(Overtime)" under Usability group.

Menus:
Human Resources/Overtimes
Human Resources/Overtimes/Overtime Requests
Human Resources/Overtimes/Overtime Requests to Approve
Human Resources/Overtimes/Overtime Requests to Approve By Department
Human Resources/Overtimes/Multiple Overtime Requests
Human Resources/Overtimes/Multiple Requests to Approve
Human Resources/Overtimes/Multiple Requests to Approve By Department
  ''',
    'depends':['hr', 'hr_payroll'],
    'data' : [
              'security/overtime_security.xml',
              'security/ir.model.access.csv',
              'views/hr_overtime_view.xml',
              'views/hr_overtime_multiple_view.xml',
              'views/hr_view.xml',
              'data/ot_salary_rule_data.xml',
              
              ],
    'installable':True,
    'auto_install':False

}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
