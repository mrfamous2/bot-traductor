import discord
import os
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

# Cargar variables de entorno
load_dotenv()

# Configurar intents
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Evento cuando el bot está listo
@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}')

# Evento cuando llega un mensaje
@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith('!t'):
        args = message.content.split(' ')

        if len(args) < 3:
            await message.channel.send("Uso: !t <idioma> <texto>")
            return

        idioma = args[1]
        texto = ' '.join(args[2:])

        try:
            traduccion = GoogleTranslator(
                source='auto',
                target=idioma
            ).translate(texto)

            await message.channel.send(traduccion)

        except Exception as e:
            print(e)
            await message.channel.send("Error al traducir 😢")

# Ejecutar bot
client.run(os.getenv("TOKEN"))