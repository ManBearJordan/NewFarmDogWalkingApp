from waitress import serve

# Your project package is 'newfarm' (as per manage.py / settings module)
from newfarm.wsgi import application

# Bind only to localhost; IIS terminates TLS and reverse-proxies to us.
# Threads=8 is plenty for this workload; tweak if needed.
serve(
    application,
    listen='127.0.0.1:8000',
    threads=8,
    ident='nfdw'
)
