import discord
import os
import psutil
import time
import requests
import re
import logging

from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()
start_time = time.time()

# =========================
# CONFIGURACION DISCORD
# =========================
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# =========================
# CONFIGURACION LOGGER
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)

# Se ignoran logs INFO de discord. Solo mostrara WARNING y ERROR
logging.getLogger("discord.gateway").setLevel(logging.WARNING)

logger = logging.getLogger("NozomiBot")

start_time = time.time()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# =========================
# HELPERS CLIMA
# =========================
WMO_CODES = {
    0:  ("☀️",  "Despejado"),
    1:  ("🌤️", "Mayormente despejado"),
    2:  ("⛅",  "Parcialmente nublado"),
    3:  ("☁️",  "Nublado"),
    45: ("🌫️", "Niebla"),
    48: ("🌫️", "Niebla con escarcha"),
    51: ("🌦️", "Llovizna ligera"),
    53: ("🌦️", "Llovizna moderada"),
    55: ("🌧️", "Llovizna intensa"),
    61: ("🌧️", "Lluvia ligera"),
    63: ("🌧️", "Lluvia moderada"),
    65: ("🌧️", "Lluvia intensa"),
    71: ("🌨️", "Nevada ligera"),
    73: ("🌨️", "Nevada moderada"),
    75: ("❄️",  "Nevada intensa"),
    77: ("🌨️", "Granizo fino"),
    80: ("🌦️", "Chubascos ligeros"),
    81: ("🌧️", "Chubascos moderados"),
    82: ("⛈️",  "Chubascos intensos"),
    85: ("🌨️", "Chubascos de nieve"),
    86: ("❄️",  "Chubascos de nieve intensos"),
    95: ("⛈️",  "Tormenta eléctrica"),
    96: ("⛈️",  "Tormenta con granizo"),
    99: ("⛈️",  "Tormenta con granizo intenso"),
}

def describir_viento(kmh):

    if kmh < 1:
        return "Calma"

    elif kmh < 6:
        return "Ventolina"

    elif kmh < 20:
        return "Brisa ligera"

    elif kmh < 40:
        return "Brisa moderada"

    elif kmh < 62:
        return "Viento fuerte"

    elif kmh < 75:
        return "Temporal"

    else:
        return "Huracán"

def direccion_viento(grados):

    puntos = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]

    return puntos[round(grados / 45) % 8]

def uv_descripcion(uv):

    if uv <= 2:
        return "Bajo"

    elif uv <= 5:
        return "Moderado"

    elif uv <= 7:
        return "Alto"

    elif uv <= 10:
        return "Muy alto"

    else:
        return "Extremo"

# =========================
# HELPERS TEXTO
# =========================
def limpiar_texto(texto):

    if not texto:
        return ""

    trans = str.maketrans({

        'á': 'a',
        'é': 'e',
        'í': 'i',
        'ó': 'o',
        'ú': 'u',

        'Á': 'a',
        'É': 'e',
        'Í': 'i',
        'Ó': 'o',
        'Ú': 'u',

        'ü': 'u',
        'Ü': 'u',

        'Ñ': 'n',
        'ñ': 'n',

        'Ō': 'o',
        'ō': 'o'
    })

    return texto.lower().translate(trans).strip()

# =========================
# BOT TRADUCTOR
# =========================

# =========================
# TRADUCTOR GOOGLE
# =========================
def traductor_google(idioma, texto):

    traduccion = GoogleTranslator(
        source='auto',
        target=idioma
        ).translate(texto)
    return traduccion

# =========================
# TRADUCTOR DEEPL
# =========================
def traductor_deepl(idioma, texto):
    return

# =========================
# BOT CLIMA
# =========================

# =========================
# OBTENER COORDENADAS
# =========================
def obtener_ciudad(ciudad, filtros):
    res = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={limpiar_texto(ciudad)}&count=10&language=es",
        timeout=10
    )

    # Si no es codigo 2xx arroja error
    res.raise_for_status()

    # Convierte respuesta a JSON
    response = res.json()
    
    # Devuelve un array vacio si no hay ciudades
    if "results" not in response or not response["results"]:
        return []
    
    ciudades = response["results"]

    # Quitamos el registro que es un pais (id es igual a country_id)
    ciudades = [r for r in ciudades if r.get("id") != r.get("country_id")]

    # Quitamos los registros que no estan relacionados a un pais (country o country_id no existen en el elemento)
    ciudades = [r for r in ciudades if "country" in r or "country_id" in r]

    # Quitamos los registros que no contienen el nombre de la ciudad
    ciudades = [r for r in ciudades if limpiar_texto(ciudad) in limpiar_texto(r.get("name"))]

    # Si ciudades tiene mas de un 1 registro y hay filtros, filtramos segun los filtros
    if len(ciudades) > 1 and filtros:
        for filtro in filtros:
            ciudades = [
                r for r in ciudades
                if limpiar_texto(filtro.lower()) in limpiar_texto(r.get("country").lower())
                or limpiar_texto(filtro.lower()) in limpiar_texto(r.get("country_code").lower())
                or "admin1" in r and limpiar_texto(filtro.lower()) in limpiar_texto(r.get("admin1").lower())
                or "admin2" in r and limpiar_texto(filtro.lower()) in limpiar_texto(r.get("admin2").lower())
                or "admin3" in r and limpiar_texto(filtro.lower()) in limpiar_texto(r.get("admin3").lower())
            ]

    # Si ciudades tiene mas de un 1 registro, filtramos todo que no sea una ciudad con feature_code PPL o similar
    # Solo en caso de que el registro sea solo 1 lo dejamos pasar solo por curiosidad (porque existe Viña Del Mar Airport y Tokyo Disney Land)
    if len(ciudades) > 1:
        ciudades = [r for r in ciudades if "PPL" in r.get("feature_code", "PPL")]

    return ciudades

# =========================
# OBTENER CLIMA
# =========================
def obtener_clima(latitude, longitude):

    res = requests.get(
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        f"dew_point_2m,precipitation,weather_code,surface_pressure,"
        f"wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
        f"cloud_cover,visibility,uv_index"
        f"&daily=temperature_2m_max,temperature_2m_min,"
        f"precipitation_sum,sunshine_duration"
        f"&timezone=auto",
        timeout=10
    )
    res.raise_for_status()
    return res.json()

# =========================
# FORMATEAR CLIMA
# =========================
def formato_clima(nombre, current, daily):
    codigo = current.get("weather_code", 0)
    emoji, estado = WMO_CODES.get(codigo, ("🌡️", "Desconocido"))
 
    temp        = current["temperature_2m"]
    sensacion   = current["apparent_temperature"]
    humedad     = current["relative_humidity_2m"]
    viento_kmh  = current["wind_speed_10m"]
    racha       = current["wind_gusts_10m"]
    dir_grados  = current["wind_direction_10m"]
    lluvia      = current["precipitation"]
    presion     = current["surface_pressure"]
    visib       = current.get("visibility")
    uv          = current.get("uv_index")
    nubosidad   = current.get("cloud_cover")
    punto_rocio = current.get("dew_point_2m")
 
    dir_texto   = direccion_viento(dir_grados)
    viento_desc = describir_viento(viento_kmh)
 
    temp_max  = daily["temperature_2m_max"][0]
    temp_min  = daily["temperature_2m_min"][0]
    lluvia_d  = daily["precipitation_sum"][0]
    sol_seg   = daily.get("sunshine_duration", [None])[0]
    sol_horas = round(sol_seg / 3600, 1) if sol_seg is not None else None
 
    lineas = [
        f"**🌍 {nombre}**",
        f"{emoji} **{estado}**",
        "",
        f"🌡️ **Temperatura:** {temp}°C  (sensación {sensacion}°C)",
        f"🔺 Máx: {temp_max}°C  🔻 Mín: {temp_min}°C",
        "",
        f"💧 **Humedad:** {humedad}%",
    ]
    if punto_rocio is not None:
        lineas.append(f"🌫️ **Punto de rocío:** {punto_rocio}°C")
    lineas += [
        "",
        f"💨 **Viento:** {viento_kmh} km/h ({dir_texto}) — {viento_desc}",
        f"🌬️ **Racha máx:** {racha} km/h",
        "",
        f"🌧️ **Precipitación actual:** {lluvia} mm",
        f"🗓️ **Precipitación hoy:** {lluvia_d} mm",
        "",
        f"🔵 **Presión:** {round(presion)} hPa",
    ]
    if nubosidad is not None:
        lineas.append(f"☁️ **Nubosidad:** {nubosidad}%")
    if visib is not None:
        lineas.append(f"👁️ **Visibilidad:** {round(visib / 1000, 1)} km")
    if uv is not None:
        lineas.append(f"🔆 **Índice UV:** {uv} ({uv_descripcion(uv)})")
    if sol_horas is not None:
        lineas.append(f"🌞 **Horas de sol hoy:** {sol_horas} h")
 
    return "\n".join(lineas)


# =========================
# VOYAGER
# =========================
def obtener_voyager(nombre_sonda, command_id):

    try:

        url = (

            f"https://ssd.jpl.nasa.gov/api/horizons.api?"

            f"format=text"

            f"&COMMAND='{command_id}'"

            f"&OBJ_DATA='YES'"
        )

        res = requests.get(
            url,
            timeout=15
        )

        texto = res.text

        nombre_match = re.search(

            r"Target body name:\s*(.*?)\s*\(",

            texto
        )

        nombre_real = (

            nombre_match.group(1).strip()

            if nombre_match

            else nombre_sonda
        )

        if command_id == "-31":

            distancia = "≈ 25 mil millones km"

            velocidad = "≈ 61.000 km/h"

            señal = "≈ 23 horas luz"

        else:

            distancia = "≈ 21 mil millones km"

            velocidad = "≈ 55.000 km/h"

            señal = "≈ 19 horas luz"

        return (

            f"🚀 **{nombre_real}**\n"

            f"🌌 Estado: Espacio interestelar\n"

            f"📍 Distancia aprox: {distancia}\n"

            f"💨 Velocidad aprox: {velocidad}\n"

            f"📡 Tiempo señal: {señal}\n"

            f"📅 Lanzamiento: 1977\n"

            f"🛰️ Fuente: NASA JPL Horizons"
        )

    except Exception as e:

        print(e)

        return "⚠️ Error obteniendo datos Voyager."

# =========================
# BOTSTATS
# =========================    
def obtener_botstats():
    uptime_seconds = int(time.time() - start_time)

    # =========================
    # HORAS UPTIME
    # =========================

    # Calculamos los dias, y el residuo va a las horas
    dias = uptime_seconds // 86400  # 86400 segundos tiene un día
    horas_residuo = uptime_seconds % 86400

    h = horas_residuo // 3600
    m = (horas_residuo % 3600) // 60
    s = horas_residuo % 60

    if dias > 0:
        uptime_str = f"{dias}d {h}h {m}m"
    else:
        uptime_str = f"{h}h {m}m {s}s"

    # =========================
    # CPU
    # =========================

    cpu = psutil.cpu_percent(interval=1)

    # =========================
    # TEMPERATURA CPU
    # =========================
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Si es una Raspberry Pi, vamos directo a buscar cpu_thermal
            if "cpu_thermal" in temps and temps["cpu_thermal"]:
                temp_actual = temps["cpu_thermal"][0].current
                temp_cpu = f"{temp_actual}°C (cpu_thermal)"
            # Caso contrario se itera en las temperaturas y toma el primer elemento
            else:
                for nombre, entradas in temps.items():
                    if entradas:
                        temp_actual = entradas[0].current
                        temp_cpu = f"{temp_actual}°C ({nombre})"
                        break
                else:
                    temp_cpu = "No disponible"
        else:
            temp_cpu = "No disponible"
    except Exception:
        temp_cpu = "No disponible"

    # =========================
    # RAM
    # =========================
    
    ram = psutil.virtual_memory()
    if ram.used < 1024 ** 3:
        ram_usage_text = f"{round(ram.used / (1024 ** 2), 1)} MB"
        ram_total_text = f"{round(ram.total / (1024 ** 2), 1)} MB"
    else:
        ram_usage_text = f"{round(ram.used / 1024 ** 3, 2)} GB"
        ram_total_text = f"{round(ram.total / 1024 ** 3, 2)} GB"

    # =========================
    # CARGA
    # =========================

    if hasattr(os, "getloadavg"):
        load_text = f"{round(os.getloadavg()[0], 2)} (1m)"
    else:
        load_text = "No disponible"

    return (
        f"📊 **Estado del bot:**\n"
        f"⏱️ Uptime: {uptime_str}\n"
        f"🧠 CPU: {cpu}%\n"
        f"🌡️ Temp CPU: {temp_cpu}\n"
        f"💾 Uso de RAM: {ram.percent}% ({ram_usage_text}) | RAM Total: {ram_total_text} \n"
        f"📈 Load: {load_text}"
    )

# =========================
# BOT LISTO
# =========================
@client.event
async def on_ready():

    print(f'Bot conectado como {client.user}')

# =========================
# MENSAJES
# =========================
@client.event
async def on_message(message):

    if message.author.bot:
        return

    # =========================
    # BOT STATS
    # =========================
    if message.content.startswith('!botstats'):

        await message.channel.send(obtener_botstats())

        return

    # =========================
    # TRADUCCION
    # =========================
    if message.content.startswith('!t '):

        try:
            args = message.content.split(' ')
            if len(args) < 3:
                await message.channel.send("Uso: `!t <idioma> <texto>`")
                return

            idioma = args[1]

            texto = ' '.join(args[2:])

            traduccion = traductor_google(idioma, texto)

            logger.info(f"Bot Traductor: Idioma: '{idioma}' | Texto: '{texto[:50]}...'")
            await message.channel.send(f"🌐 ({idioma}) {traduccion}")

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "Desconocido"
            logger.warning(f"Bot Traductor: Error HTTP {status} detectado en la traducción para el idioma '{idioma}'")
            await message.channel.send("⚠️ Error al traducir")
        except requests.exceptions.Timeout:
            logger.error(f"Bot Traductor: Timeout de red esperando respuesta en la traducción para '{idioma}'")
            await message.channel.send("⏳ La consulta tardó demasiado. Intentelo denuevo")
        except Exception as e:
            logger.exception(f"Bot Traductor: Error imprevisto en el orquestador de traducción: {e}")
            await message.channel.send("💥 Error con el bot de traducción")

        return

    # =========================
    # VOYAGER
    # =========================
    if message.content.startswith('!voyager'):

        if message.content.strip() == '!voyager1':

            datos = obtener_voyager(
                "Voyager 1",
                "-31"
            )

            await message.channel.send(datos)

            return

        elif message.content.strip() == '!voyager2':

            datos = obtener_voyager(
                "Voyager 2",
                "-32"
            )

            await message.channel.send(datos)

            return

        elif message.content.strip() == '!voyager compare':

            v1 = obtener_voyager(
                "Voyager 1",
                "-31"
            )

            v2 = obtener_voyager(
                "Voyager 2",
                "-32"
            )

            await message.channel.send(

                f"🛰️ **Comparación Voyager**\n\n"

                f"{v1}\n\n"

                f"{v2}"
            )

            return

        else:

            await message.channel.send(

                "🚀 Comandos Voyager:\n"

                "`!voyager1`\n"

                "`!voyager2`\n"

                "`!voyager compare`"
            )

            return

    # =========================
    # CLIMA
    # =========================
    if message.content.startswith("!clima"):
        try:
            contenido = message.content
            mensaje_procesado = ' '.join(contenido.split(' ')[1:]).strip()
            if not mensaje_procesado:
                await message.channel.send(
                    "Uso:\n"
                    "`!clima ciudad`\n"
                    "o\n"
                    "`!clima ciudad, <pais, estado, region, prefectura, provincia, etc....>`"
                )
                return
            
            # Si pillamos una coma separamos el mensaje en 2, el primero para la ciudad y el segundo un arreglo con filtros
            # Separamos por comas y limpiamos espacios de cada parte
            partes = [p.strip() for p in mensaje_procesado.split(',')]
            # El primero siempre es la ciudad
            ciudad = partes[0]
            # El resto son filtros (puede ser una lista vacía si no hay comas)
            filtros = partes[1:]
            ciudad_response = obtener_ciudad(ciudad, filtros)
            # Si el array esta vacio (no encontro la ciudad)
            if len(ciudad_response) == 0:
                logger.warning(f"Bot Clima: No se encontraron resultados para '{ciudad}'")
                await message.channel.send("❌ Ciudad no encontrada")
                return
            
            # Si el array tiene mas de 1 elemento (encontro mas de 1 ciudad)
            elif len(ciudad_response) > 1:
                logger.info(f"Bot Clima: Múltiples opciones ({len(ciudad_response)}) encontradas")
                opciones = []
                for i, r in enumerate(ciudad_response[:5]):
                    n = r['name']
                    a1 = r.get('admin1', '')
                    a2 = r.get('admin2', '')
                    a3 = r.get('admin3', '')
                    p = r.get('country', '')

                    partes_loc = [n]
                    if a3 and a3.lower() != n.lower(): partes_loc.append(a3)
                    if a2 and a2.lower() != n.lower() and a2 != a3: partes_loc.append(a2)
                    if a1 and a1.lower() != n.lower() and a1 != a2: partes_loc.append(a1)
                    
                    ubicacion = ", ".join(partes_loc)

                    linea = f"**{i+1}.** {ubicacion} — {p}"
                    opciones.append(linea)
                    
                cuerpo_final = "\n".join(opciones)

                await message.channel.send(
                    f"⚠️ Hay varias ciudades llamadas "
                    f"**{ciudad}**.\n\n"

                    f"Usa:\n"

                    f"`!clima ciudad, <pais, estado, region, prefectura, provincia, etc....>`\n\n"

                    f"{cuerpo_final}"
                )
                return
            
            # Desde aqui se asume que hay 1 ciudad
            ciudad_filtrada = ciudad_response[0]
            ciudad_limpia = {
                "nombre": ciudad_filtrada.get("name"),
                "pais": ciudad_filtrada.get("country"),
                "region": ciudad_filtrada.get("admin1", ""),
                "latitud": ciudad_filtrada.get("latitude"),
                "longitud": ciudad_filtrada.get("longitude"),
            }
            clima_response = obtener_clima(ciudad_limpia.get("latitud"), ciudad_limpia.get("longitud"))
            nombre_completo = f"{ciudad_limpia.get("nombre")}, {ciudad_limpia.get("region")}, {ciudad_limpia.get("pais")}" if ciudad_limpia.get("region") else f"{ciudad_limpia.get("nombre")}, {ciudad_limpia.get("pais")}"
            clima = formato_clima(nombre_completo, clima_response.get("current"), clima_response.get("daily"))

            logger.info(f"Bot Clima: Renderizado exitoso para {nombre_completo}")
            await message.channel.send(clima)

            return

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            logger.warning(f"Bot Clima: Error HTTP {status} detectado en el flujo del clima para '{ciudad}'")
            await message.channel.send("⚠️ Error obteniendo el clima")
        except requests.exceptions.Timeout:
            logger.error(f"Bot Clima: Timeout de red procesando el comando para '{ciudad}'")
            await message.channel.send("⏳ La consulta tardó demasiado. Intentelo denuevo")
        except Exception as e:
            logger.exception(f"Bot Clima: Error imprevisto en el orquestador del clima: {e}")
            await message.channel.send("💥 Error con el bot del clima")

client.run(os.getenv("TOKEN"))
