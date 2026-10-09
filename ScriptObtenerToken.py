"""
Script para obtener un access_token OAuth2 de WordPress.com.
Se ejecuta UNA SOLA VEZ (o cuando el token se revoque/caduque).

Requisitos previos:
  1. Haber creado una app en https://developer.wordpress.com/apps/
  2. Redirect URL configurada exactamente como: http://localhost:8888/callback
  3. Tener CLIENT_ID y CLIENT_SECRET de esa app
"""

import http.server
import socketserver
import urllib.parse
import webbrowser
import requests
import threading

# --- CONFIGURA ESTOS DATOS ---
REDIRECT_URI = "http://localhost:8888/callback"
CLIENT_ID = "143308"
CLIENT_SECRET = "3qhkFueqyq2M4bmqtBjEuWVhmRTOMt7QoLUNaQK4Mpghg4e2E9zOmOjGaIAnbpVi"

PUERTO = 8888
codigo_recibido = {"code": None}


class ManejadorCallback(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            codigo_recibido["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h2>Autorizacion completada. Ya puedes cerrar esta pestana.</h2>".encode("utf-8")
            )
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No se recibio codigo de autorizacion.")

    def log_message(self, format, *args):
        pass  # silencia el log del servidor local


def obtener_codigo_autorizacion():
    url_autorizacion = (
        "https://public-api.wordpress.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        "&response_type=code"
        "&scope=global"
    )

    print("Abriendo el navegador para que autorices la aplicacion...")
    print(f"Si no se abre solo, entra manualmente en:\n{url_autorizacion}\n")
    webbrowser.open(url_autorizacion)

    with socketserver.TCPServer(("localhost", PUERTO), ManejadorCallback) as httpd:
        print(f"Esperando autorizacion en http://localhost:{PUERTO}/callback ...")
        httpd.handle_request()  # atiende UNA sola peticion y sigue

    return codigo_recibido["code"]


def intercambiar_codigo_por_token(codigo):
    url_token = "https://public-api.wordpress.com/oauth2/token"
    datos = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "code": codigo,
    }
    respuesta = requests.post(url_token, data=datos)
    respuesta.raise_for_status()
    return respuesta.json()


if __name__ == "__main__":
    codigo = obtener_codigo_autorizacion()

    if not codigo:
        print("No se obtuvo el codigo de autorizacion. Revisa la Redirect URL configurada en la app.")
    else:
        print(f"Codigo recibido: {codigo}")
        datos_token = intercambiar_codigo_por_token(codigo)

        access_token = datos_token.get("access_token")
        print("\n¡Token obtenido con exito!")
        print(f"access_token: {access_token}")
        print(f"blog_id: {datos_token.get('blog_id')}")
        print(f"blog_url: {datos_token.get('blog_url')}")

        # Guardamos el token en un archivo local para reutilizarlo
        with open("wp_token_alt.txt", "w") as f:
            f.write(access_token)
        print("\nToken guardado en 'wp_token_alt.txt'. Guardalo en un lugar seguro (no lo subas a git).")
