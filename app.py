import logging
import socket

from app import create_app


# ------------------------------------------------------------
# Suppress Flask / Werkzeug request logging
# ------------------------------------------------------------

logging.getLogger("werkzeug").disabled = True
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)


application = create_app()


def get_ip_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("10.255.255.255", 1))
        ip_address = sock.getsockname()[0]
    except Exception:
        ip_address = "127.0.0.1"
    finally:
        sock.close()

    return ip_address


if __name__ == "__main__":

    ip_address = get_ip_address()

    print()
    print("========================================")
    print(" SMART SOUND BOWLS")
    print("========================================")
    print()
    print(f"IP Address : {ip_address}")
    print(f"Web UI     : http://{ip_address}:5000")
    print("Hostname   : http://rpi.local:5000")
    print()
    print("Press Ctrl+C to stop")
    print()

    application.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )
