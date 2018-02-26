import os

def application(environ, start_response):
    os.environ['CONFIG_FILE'] = environ['CONFIG_FILE']
    from dlrn.api import app
    return app(environ, start_response)
