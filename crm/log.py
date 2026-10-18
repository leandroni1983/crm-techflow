import time


def log(msg):
    """Una línea de log con hora (va a stdout: `docker compose logs crm`)."""
    print(time.strftime("%H:%M:%S ") + str(msg), flush=True)
