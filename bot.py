import discord
import os
import psutil
import time
import requests
import re

from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

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

def formato_clima(nombre, current, daily):

    codigo = current.get("weather_code", 0)

    emoji, estado = WMO_CODES.get(
        codigo,
        ("🌡️", "Desconocido")
    )

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

    temp_max = daily["temperature_2m_max"][0]
    temp_min = daily["temperature_2m_min"][0]

    lluvia_d = daily["precipitation_sum"][0]

    sol_seg = daily.get(
        "sunshine_duration",
        [None]
    )[0]

    sol_horas = (
        round(sol_seg / 3600, 1)
        if sol_seg is not None
        else None
    )

    lineas = [

        f"**🌍 {nombre}**",

        f"{emoji} **{estado}**",

        "",

        f"🌡️ **Temperatura:** {temp}°C "
        f"(sensación {sensacion}°C)",

        f"🔺 Máx: {temp_max}°C  "
        f"🔻 Mín: {temp_min}°C",

        "",

        f"💧 **Humedad:** {humedad}%"
    ]

    if punto_rocio is not None:

        lineas.append(
            f"🌫️ **Punto de rocío:** "
            f"{punto_rocio}°C"
        )

    lineas += [

        "",

        f"💨 **Viento:** "
        f"{viento_kmh} km/h "
        f"({dir_texto}) — {viento_desc}",

        f"🌬️ **Racha máx:** "
        f"{racha} km/h",

        "",

        f"🌧️ **Precipitación actual:** "
        f"{lluvia} mm",

        f"🗓️ **Precipitación hoy:** "
        f"{lluvia_d} mm",

        "",

        f"🔵 **Presión:** "
        f"{round(presion)} hPa"
    ]

    if nubosidad is not None:

        lineas.append(
            f"☁️ **Nubosidad:** "
            f"{nubosidad}%"
        )

    if visib is not None:

        lineas.append(
            f"👁️ **Visibilidad:** "
            f"{round(visib / 1000, 1)} km"
        )

    if uv is not None:

        lineas.append(
            f"🔆 **Índice UV:** "
            f"{uv} ({uv_descripcion(uv)})"
        )

    if sol_horas is not None:

        lineas.append(
            f"🌞 **Horas de sol hoy:** "
            f"{sol_horas} h"
        )

    return "\n".join(lineas)

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
# OBTENER CLIMA
# =========================

def obtenerClima(ciudad, filtros):

    geo_res = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?"
        f"name={limpiar_texto(ciudad)}&count=10&language=es",
        timeout=10
    ).json()

    if "results" not in geo_res:

        return "❌ Ciudad no encontrada."

    if not geo_res["results"]:

        return "❌ Ciudad no encontrada."

    resultados = geo_res["results"]

    resultados = [

        r for r in resultados

        if r.get("id") != r.get("country_id")
    ]

    resultados = [

        r for r in resultados

        if "country" in r or "country_id" in r
    ]

    resultados = [

        r for r in resultados

        if limpiar_texto(ciudad)
        in limpiar_texto(r.get("name"))
    ]

    if len(resultados) > 1 and filtros:

        for filtro in filtros:

            resultados = [

                r for r in resultados

                if limpiar_texto(filtro.lower())
                in limpiar_texto(
                    r.get("country", "").lower()
                )

                or limpiar_texto(filtro.lower())
                in limpiar_texto(
                    r.get("country_code", "").lower()
                )

                or (
                    "admin1" in r
                    and limpiar_texto(filtro.lower())
                    in limpiar_texto(
                        r.get("admin1", "").lower()
                    )
                )

                or (
                    "admin2" in r
                    and limpiar_texto(filtro.lower())
                    in limpiar_texto(
                        r.get("admin2", "").lower()
                    )
                )

                or (
                    "admin3" in r
                    and limpiar_texto(filtro.lower())
                    in limpiar_texto(
                        r.get("admin3", "").lower()
                    )
                )
            ]

    if len(resultados) > 1:

        resultados = [

            r for r in resultados

            if "PPL"
            in r.get("feature_code", "PPL")
        ]

    if len(resultados) > 1:

        opciones = []

        for i, r in enumerate(resultados[:5]):

            n  = r['name']
            a1 = r.get('admin1', '')
            a2 = r.get('admin2', '')
            a3 = r.get('admin3', '')
            p  = r.get('country', '')

            partes_loc = [n]

            if a3 and a3.lower() != n.lower():
                partes_loc.append(a3)

            if a2 and a2.lower() != n.lower():
                if a2 != a3:
                    partes_loc.append(a2)

            if a1 and a1.lower() != n.lower():
                if a1 != a2:
                    partes_loc.append(a1)

            ubicacion = ", ".join(partes_loc)

            linea = (
                f"**{i+1}.** "
                f"{ubicacion} — {p}"
            )

            opciones.append(linea)

        cuerpo_final = "\n".join(opciones)

        return (
            f"⚠️ Hay varias ciudades llamadas "
            f"**{ciudad}**.\n\n"

            f"Usa:\n"

            f"`!clima ciudad, pais/provincia`\n\n"

            f"{cuerpo_final}"
        )

    elif not resultados:

        return "❌ Ciudad no encontrada."

    r = resultados[0]

    lat = r["latitude"]
    lon = r["longitude"]

    nombre = r["name"]

    pais = r["country"]

    region = r.get("admin1", "")

    w = requests.get(

        f"https://api.open-meteo.com/v1/forecast?"

        f"latitude={lat}&longitude={lon}"

        f"&current="
        f"temperature_2m,"
        f"apparent_temperature,"
        f"relative_humidity_2m,"
        f"dew_point_2m,"
        f"precipitation,"
        f"weather_code,"
        f"surface_pressure,"
        f"wind_speed_10m,"
        f"wind_direction_10m,"
        f"wind_gusts_10m,"
        f"cloud_cover,"
        f"visibility,"
        f"uv_index"

        f"&daily="
        f"temperature_2m_max,"
        f"temperature_2m_min,"
        f"precipitation_sum,"
        f"sunshine_duration"

        f"&timezone=auto",

        timeout=10

    ).json()

    nombre_completo = (

        f"{nombre}, {region}, {pais}"

        if region

        else f"{nombre}, {pais}"
    )

    return formato_clima(

        nombre_completo,

        w["current"],

        w["daily"]
    )

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

        args = message.content.split(' ')

        if len(args) < 3:

            await message.channel.send(
                "Uso: `!t <idioma> <texto>`"
            )

            return

        idioma = args[1]

        texto = ' '.join(args[2:])

        try:

            traduccion = GoogleTranslator(

                source='auto',

                target=idioma

            ).translate(texto)

            await message.channel.send(
                f"🌐 ({idioma}) {traduccion}"
            )

        except Exception as e:

            print(e)

            await message.channel.send(
                "⚠️ Error al traducir"
            )

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

    if message.content.startswith('!clima'):

        mensaje = ' '.join(
            message.content.split(' ')[1:]
        ).strip()

        if not mensaje:

            await message.channel.send(

                "Uso:\n"

                "`!clima ciudad`\n"

                "o\n"

                "`!clima ciudad, pais/provincia`"
            )

            return

        try:

            partes = [

                p.strip()

                for p in mensaje.split(',')
            ]

            ciudad = partes[0]

            filtros = partes[1:]

            respuesta = obtenerClima(
                ciudad,
                filtros
            )

            await message.channel.send(
                respuesta
            )

        except Exception as e:

            print(e)

            await message.channel.send(
                "⚠️ Error obteniendo clima."
            )

        return

client.run(os.getenv("TOKEN"))
