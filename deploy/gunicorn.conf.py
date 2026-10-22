# Gunicorn sozlamasi: systemd orqali ishga tushiriladi (deploy/socialpuls.service).
import multiprocessing

bind = "unix:/run/socialpuls/gunicorn.sock"
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)
worker_class = "sync"
timeout = 120          # PDF/Excel eksport va HEMIS sinxroni uchun
graceful_timeout = 30
max_requests = 1000    # xotira oqishidan himoya
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "127.0.0.1"
