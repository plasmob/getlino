# -*- coding: UTF-8 -*-
from lino_noi.lib.noi.settings import *

import logging
logging.getLogger('weasyprint').setLevel("ERROR") # see #1462


class Site(Site):
    title = "prjname"
    server_url = "https://myprjname.lino-framework.org"

SITE = Site(globals())

# locally override attributes of individual plugins
# SITE.plugins.finan.suggest_future_vouchers = True

# MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'prjname', #database name
        'USER': 'lino',
        'PASSWORD': '1234',
        'HOST': 'localhost',                  
        'PORT': 3306,
        
        'OPTIONS': {
           "init_command": "SET storage_engine=MyISAM",
        }
        
}
}
