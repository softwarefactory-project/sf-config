import os
import sys

# Not happy to do that here but mod_wsgi is python 2.7 here
# As far as I saw the API respond w/o issue. Let's keep
# that like that until we find a real issue with it.

sys.path.append('/opt/rh/rh-python35/root/lib/python3.5/site-packages/')

def application(environ, start_response):
    os.environ['CONFIG_FILE'] = environ['CONFIG_FILE']
    from dlrn.api import app
    return app(environ, start_response)
