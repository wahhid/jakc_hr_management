# -*- coding:utf-8 -*-
#
#
#    Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

{
    'name': 'Employee Shift Scheduling',
    'version': '10.0.1.0',
    'category': 'Generic Modules/Human Resources',
    'description': """
Employee Shift Scheduling
=========================

Easily create, manage, and track employee schedules.
    """,
    'author': "Jakc Labs",
    'website': 'http://www.jakc-labs.com',
    'license': 'AGPL-3',
    'depends': [
        'hr_attendance',
        'hr_contract',
        'hr_holidays',
    ],
    "external_dependencies": {
        'python': ['dateutil'],
    },
    'data': [
        'views/jakc_hr_schedule_view.xml',
        'views/hr_attendance_view.xml',
        'views/resource_view.xml',
    ],
    'test': [
    ],
    'application': True,
    'installable': True,
}
