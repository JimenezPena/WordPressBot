import feedparser
import requests
import time
import json

import re
import html

import os
#from openai import OpenAI
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Cargamos las variables de entorno del archivo .env (tu API Key)
load_dotenv()

# Inicializamos el cliente de OpenAI
# Automáticamente buscará la variable 'OPENAI_API_KEY' en tu sistema o archivo .env
#client = OpenAI()
client = genai.Client()

# --- CONFIGURACIÓN ---

AUTORES_EXCLUIDOS = os.getenv("AUTORES_EXCLUIDOS")

URL_FEED_RSS 		= os.getenv("URL_FEED_RSS")			#Ex: "https://yourwebsite.wordpress.com/feed/"
WP_USER			= os.getenv("WP_USER")
WP_APP_URL	 	= os.getenv("WP_APP_URL")			
WP_APP_PASSWORD	= os.getenv("WP_APP_PASSWORD")		#Ex: "abcd efgh ijkl mnop" --> this is the expected format
WP_ACCESS_TOKEN 	= os.getenv("WP_ACCESS_TOKEN")

# Archivo local para no repetir comentarios en relatos viejos
DB_POSTS_PROCESADOS = "posts_procesados.json"


def limpiar_html_wordpress(texto_sucio):
    """
    Limpia el HTML de WordPress preservando la estructura de párrafos 
    y saltos de línea para que el relato no pierda su forma.
    """
    if not texto_sucio:
        return ""
        
    # 1. Eliminar comentarios internos de WordPress (como <!-- wp:paragraph -->)
    texto = re.sub(r'<!--.*?-->', '', texto_sucio)
    
    # 2. Convertir etiquetas de párrafo y saltos HTML en saltos de línea reales
    texto = re.sub(r'</p>', '\n\n', texto)  # Fin de párrafo = dos saltos
    texto = re.sub(r'<br\s*/?>', '\n', texto) # Salto de línea simple
    
    # 3. Eliminar cualquier otra etiqueta HTML restante (<[^>]+>)
    texto = re.sub(r'<[^>]+>', '', texto)
    
    # 4. Convertir entidades HTML (&aacute;, &nbsp;, etc.) a texto normal
    texto = html.unescape(texto)
    
    # 5. Limpieza fina de espacios vacíos:
    # Eliminamos espacios duplicados en la misma línea, pero dejamos los saltos de línea intactos
    lineas = []
    for linea in texto.splitlines():
        linea_limpia = re.sub(r'[ \t]+', ' ', linea).strip()
        lineas.append(linea_limpia)
        
    # Juntamos las líneas y reducimos si hay más de dos saltos seguidos acumulados
    texto_final = '\n'.join(lineas)
    texto_final = re.sub(r'\n{3,}', '\n\n', texto_final) # Máximo 2 saltos seguidos entre párrafos
    
    return texto_final.strip()
    
def cargar_procesados():
    try:
        with open(DB_POSTS_PROCESADOS, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def guardar_procesado(post_id):
    procesados = cargar_procesados()
    procesados.append(post_id)
    with open(DB_POSTS_PROCESADOS, "w") as f:
        json.dump(procesados, f)


def generar_comentario_falso(titulo, contenido_relato):
    #print(f"-> Enviando relato al LLM: '{titulo}'...")
    
     return f"¡Muchas gracias por compartir el relato '{titulo}'! Ha sido una lectura estupenda."
    
def generar_comentario_llm(titulo, contenido_relato):
    
    # Creamos un prompt muy específico para moldear la personalidad del bot
    prompt_sistema = (
        "Eres un lector apasionado de relatos cortos de ficción, poesía y narrativa. "
        "Tu objetivo es leer el relato que te proporciona el usuario y escribir un comentario "
        "público para el blog del autor. "
        "REGLAS ESTRICTAS:\n"
        "1. Sé crítico y constructivo.\n" 
        "2. Destaca algo específico del relato (un giro, la atmósfera, un personaje o una frase).\n"
        "3. Escribe en un personal y natural:* Habla de tú a tú, como un lector cotidiano, evitando sonar como un crítico literario, un profesor o un modelo de lenguaje.\n"
        "4. El comentario debe ser breve y al grano, entre 3 y 4 frases máximo.\n"
        "5. Lenguaje moderado: Ir a los hechos sin utilizar epítetos exagerados (nada de 'fascinante' o 'genial') ni expresiones coloquiales forzadas (como 'rollo' o 'súper').\n"
        "6. Enfoque positivo: Destaca detalles específicos que funcionen bien en el relato y omite cualquier aspecto negativo.\n"
        "7. Responde siempre en el mismo idioma en el que está escrito el relato."
    )
    
    cuerpo_mensaje = f"Título: {titulo}\n\nContenido del relato:\n{contenido_relato}"

    try:
        # Usamos gemini-2.5-flash, el modelo estándar gratuito y rápido
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=cuerpo_mensaje,
            config=types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                temperature=1.2
            )
        )
        
        comentario_final = response.text.strip()
        return comentario_final
        
    except Exception as e:
        print(f"Error al conectar con la API del LLM: {e}")
        # Devolvemos un comentario genérico de respaldo por si la API falla y no romper el flujo
        return f"¡Muchas gracias por compartir el relato '{titulo}'! Ha sido una lectura estupenda."
        

# --- PUBLICAR EN WORDPRESS ---
def publicar_comentario_wp_por_url(post_url, texto_comentario):
    # 1. Extraemos el dominio y el slug correctamente
    dominio_blog = post_url.split("//")[-1].split("/")[0]
    slug = post_url.strip().strip("/").split("/")[-1]

    # 2. La URL mágica para WordPress.com
    url_buscar_id = f"https://public-api.wordpress.com/rest/v1.1/sites/{dominio_blog}/posts/slug:{slug}"
    print(url_buscar_id)

    cabeceras = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Authorization": f"Bearer {WP_ACCESS_TOKEN}",
    }

    try:
        res = requests.get(url_buscar_id, headers=cabeceras)

        if res.status_code != 200:
            print(f"Error en WordPress.com ({res.status_code}) para el slug: {slug}")
            print(res.text)
            return

        datos_post = res.json()
        post_id = datos_post["ID"]  # Ojo: en esta API, "ID" va en mayúsculas
        print(f"¡ID encontrado con éxito!: {post_id}")

    except Exception as e:
        print(f"Error al obtener el ID en WordPress.com: {e}")
        return

    # --- PASO B: PUBLICAR COMENTARIO ---
    # OJO: el endpoint de creación necesita "/new" al final
    wp_comentarios_url = (
        f"https://public-api.wordpress.com/rest/v1.1/sites/{dominio_blog}/posts/{post_id}/replies/new"
    )
    print(wp_comentarios_url)

    payload = {"content": texto_comentario}

    response = requests.post(
        wp_comentarios_url,
        json=payload,
        headers=cabeceras,  # ya no usamos auth=(...), el Bearer va en headers
    )

    if response.status_code == 200 or response.status_code == 201:
        print(f"¡Comentario publicado con éxito en el post {post_id}!")
    else:
        print(f"Error al comentar: {response.status_code}", response.text)
        
                
# --- FLUJO PRINCIPAL ---
def ejecutar_bot():
    print("Revisando el blog\n")
    url_rss = os.environ.get("URL_FEED_RSS")
    print(f"URL a procesar: {url_rss}")
    
    try:
        # Añadimos cabeceras para fingir que somos un navegador y un timeout de 15 segundos
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        respuesta = requests.get(url_rss, headers=headers, timeout=15)
        respuesta.raise_for_status()
        
        # Parseamos el contenido descargado
        feed = feedparser.parse(respuesta.content)
        print(f"Feed descargado con éxito. Entradas encontradas: {len(feed.entries)}")
        
    except Exception as e:
        print(f"Error al descargar el RSS: {e}")
        return

    procesados = cargar_procesados()
    
    for entrada in feed.entries:
        post_url = entrada.link  # ¡Usamos la URL directa como ID!

        autor = entrada.get("author", "")
        if autor in AUTORES_EXCLUIDOS:
            continue #evitamos comentar el relato si es de un autor excluido
        
        if post_url in procesados:
            continue # Ya comentamos en este relato, saltamos al siguiente

        print(f"\n¡Nuevo relato detectado!: {entrada.title}")
        
        # Extraer el contenido del relato
        contenido_sucio = entrada.get("content", [{}])[0].get("value", entrada.summary)
        
        # ¡Limpiamos el texto aquí!
        contenido = limpiar_html_wordpress(contenido_sucio)

        # 1. Pasarlo por el LLM
        comentario = generar_comentario_llm(entrada.title, contenido)
        #comentario = generar_comentario_falso(entrada.title, contenido)
        
        print("\n\n", contenido, "\n\n       ###########      \n\n", comentario)
        #print("\n", comentario)
        
        # 2. Publicarlo en la web usando la URL
        publicar_comentario_wp_por_url(post_url, comentario)
        
        # 3. Guardar la URL en la lista de ignorar
        guardar_procesado(post_url)
        
        time.sleep(15) #El time sleep evita hacer múltiples llamadas consecutivas a la API de Google, lo que bloquea nuevas llamadas.
        
        
if __name__ == "__main__":
    # La primera vez que lo corras, marcará los posts actuales como procesados 
    # para no comentar en cosas de hace meses.
    ejecutar_bot()
