from waitress import serve
from newfarm.wsgi import application   # <-- your project package is 'newfarm'
serve(application, listen='127.0.0.1:8000', threads=8, ident='nfdw')
