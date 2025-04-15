{
    'name': 'Comisiones Servicios - Comercial',
    'version': '1.0',
    'description': '',
    'summary': '',
    'author': 'FPC Technology',
    'website': 'https://fpc-technology.com/',
    'license': 'LGPL-3',
    'category': 'sale',
    'depends': [
        'base', "sale", "account"
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'view/kanban_res_partner.xml',
        'view/aceleradores_form.xml',
        'view/comisiones_empleado.xml',
        'data/comision_data.xml',
        'wizard/wizard_comision.xml',
        'view/inherit_from_nomina.xml',
    ],
    'auto_install': False,
    'application': True,
}