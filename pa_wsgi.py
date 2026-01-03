from main import app
from a2wsgi import ASGIMiddleware

# This is the object you point to in PythonAnywhere's "WSGI configuration file"
# e.g. from pa_wsgi import application
application = ASGIMiddleware(app)
