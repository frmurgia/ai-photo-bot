import signal
import time
import datetime
import telepot
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.loop import MessageLoop
import os
import sys
import cv2
import base64
import requests
import json
import shutil
import ssl
from PIL import Image
import pdfkit

# Suppress SSL warnings (non raccomandato per l'uso in produzione)
requests.get('https://api.telegram.org', verify=False)

# Carica le variabili di configurazione dal file config.json
with open('config.json') as config_file:
    config = json.load(config_file)
    # Imposta il timestamp dell'ultima modifica
    config['last_modified'] = os.path.getmtime('config.json')

# Utilizza le variabili nel tuo script
api_key = config['openai_api_key']
telegram_bot_token = config['telegram_bot_token']
bot = telepot.Bot(telegram_bot_token)
inline_keyboard_labels = config['inline_keyboard_labels']
prompts = config['prompts']

# Variabili globali
payload = None
retry_photo = False  # Traccia se l'utente vuole rifare la foto

# Header per l'API OpenAI
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

# Percorso per il file di lock
lock_file_path = '/tmp/bot_lock'

# Funzione per rimuovere il file di lock
def remove_lock_file():
    print('Removing lock file...')
    if os.path.exists(lock_file_path):
        os.remove(lock_file_path)

# Gestione del segnale per un'uscita pulita
def signal_handler(sig, frame):
    print('Exiting...')
    remove_lock_file()
    sys.exit(0)

# Associa il gestore del segnale al segnale di interruzione
signal.signal(signal.SIGINT, signal_handler)

# Controlla se un'altra istanza è già in esecuzione
if os.path.exists(lock_file_path):
    print('Another instance is already running. Exiting...')
    sys.exit(1)

# Crea un file di lock
open(lock_file_path, 'w').close()

# Funzione per codificare l'immagine in base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Funzione per scattare e inviare una foto
def take_and_send_photo(chat_id):
    # Apri la webcam
    cap = cv2.VideoCapture(0)

    # Controlla se la webcam è aperta correttamente
    if not cap.isOpened():
        raise IOError("Unable to open the webcam")

    # Leggi un frame dalla webcam
    ret, frame = cap.read()

    # Salva l'immagine
    image_path = 'test-1.jpg'
    cv2.imwrite(image_path, frame)

    # Rilascia la webcam
    cap.release()

    # Ruota e invia la foto
    image = Image.open(image_path)
    rotated_image = image.rotate(0, expand=True)
    rotated_image_path = "rotated_image.jpg"
    rotated_image.save(rotated_image_path)

    with open(rotated_image_path, 'rb') as img:
        bot.sendPhoto(chat_id, img)

    os.remove(rotated_image_path)

    # Invia tastiera inline con i bottoni "Accept" e "Retry"
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Accept', callback_data='/accept_photo')],
        [InlineKeyboardButton(text='Retry', callback_data='/retry_photo')]
    ])
    bot.sendMessage(chat_id, 'Do you want to accept this photo or retry?', reply_markup=inline_keyboard)

# Funzione per gestire i messaggi
def handle(msg):
    global payload, retry_photo
    chat_id = msg['chat']['id']
    command = msg['text']

    print('Got command: {}'.format(command))

    if command == '/take_a_photo':
        print('Wait! I will take a photo...')
        bot.sendMessage(chat_id, 'Wait! Now I will take a photo.')
        take_and_send_photo(chat_id)

    elif command == '/time':
        bot.sendMessage(chat_id, str(datetime.datetime.now()))

    elif command == '/start':
        # Crea una risposta inline con le istruzioni del bot
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Take a Photo', callback_data='/take_a_photo')],
        ])
        bot.sendMessage(chat_id, 'Welcome to the SnapJudge!\n\nTo take a photo, use the command /take_a_photo.')

# Funzione per salvare la foto accettata
def save_accepted_photo(image_path):
    # Stampa il percorso completo del file
    full_image_path = os.path.abspath(image_path)
    print(f"Full image path: {full_image_path}")

    # Verifica se il file esiste prima di spostarlo
    if not os.path.exists(full_image_path):
        print(f"Error: File {full_image_path} not found!")
        return

    # Specifica il percorso dove salvare la foto
    accepted_folder = "accepted_photos"
    if not os.path.exists(accepted_folder):
        os.makedirs(accepted_folder)
    
    # Sposta la foto nella cartella specificata
    new_image_path = os.path.join(accepted_folder, os.path.basename(full_image_path))
    shutil.move(full_image_path, new_image_path)
    print(f"Photo saved to {new_image_path}")
    return new_image_path  # Ritorna il nuovo percorso

# Funzione per chiedere all'utente se vuole scattare di nuovo una foto
def ask_to_restart(chat_id):
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Yes', callback_data='/take_a_photo')],
        [InlineKeyboardButton(text='No', callback_data='/end_session')]
    ])
    bot.sendMessage(chat_id, 'Do you want to take another photo?', reply_markup=inline_keyboard)

# Funzione per gestire le callback (es. pressioni dei bottoni)
def on_callback_query(msg):
    global payload, retry_photo
    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')

    if query_data == '/retry_photo':
        # Se l'utente clicca "Retry", scatta una nuova foto
        bot.sendMessage(from_id, 'Okay, let\'s try again.')
        print("User selected 'Retry' - taking new photo...")
        take_and_send_photo(from_id)

    elif query_data == '/accept_photo':
        # Se l'utente accetta la foto, procedi con i prossimi passi
        bot.sendMessage(from_id, 'Great! The photo has been accepted.')
        print("User accepted the photo.")

        # Procedi con l'invio della foto all'API OpenAI
        image_path = 'test-1.jpg'

        # Salva la foto prima di rimuoverla
        new_image_path = save_accepted_photo(image_path)

        # Aggiungi un messaggio di debug per confermare che la foto è stata salvata
        print(f"Photo saved and ready to proceed: {new_image_path}")

        # Crea tastiera inline con le etichette
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f'/button{i+1}')] for i, label in enumerate(inline_keyboard_labels)
        ])

        # Invia il messaggio "Choose a judge:" con la tastiera inline
        bot.sendMessage(from_id, 'Choose a judge:', reply_markup=inline_keyboard)

        # Crea il payload con i dati necessari per l'API usando il nuovo percorso dell'immagine
        base64_image = encode_image(new_image_path)
        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": ""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }
        print("Payload created for OpenAI API")

    elif query_data.startswith('/button'):
        # Estrai il prompt corrispondente al bottone premuto
        button_index = int(query_data[-1]) - 1  # Sottrai 1 perché gli indici degli array partono da 0
        if 0 <= button_index < len(prompts):
            label = prompts[button_index]
        else:
            label = "Label not found."

        # Modifica il payload con il prompt corrente
        prompt = f"{label}"
        payload['messages'][0]['content'][0]['text'] = prompt

        # Invia la richiesta a OpenAI
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        json_data = response.json()

        content_message = json_data['choices'][0]['message']['content']

        # Invia il contenuto del messaggio al bot Telegram
        bot.sendMessage(from_id, content_message)

        print("Photo processed successfully!")
        print(content_message)

        # Chiedi se l'utente vuole scattare un'altra foto
        ask_to_restart(from_id)

        # Resetta il payload
        payload = None

    elif query_data == '/end_session':
        # L'utente ha scelto di terminare la sessione
        bot.sendMessage(from_id, 'Thank you! Session ended.')
        print("User ended the session.")

# Registra le funzioni per gestire i messaggi e le callback
MessageLoop(bot, {'chat': handle, 'callback_query': on_callback_query}).run_as_thread()
print('I am listening ...')

# Loop principale per mantenere lo script in esecuzione
try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    pass
finally:
    # Pulizia e uscita
    remove_lock_file()
    sys.exit(0)
