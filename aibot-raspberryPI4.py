# Import necessary libraries
import signal
import time
import random
import datetime
import telepot
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.loop import MessageLoop
import os
import sys
from picamera2 import Picamera2
import subprocess
import base64
import requests
import json
import textwrap 
import shutil 
import pdfkit
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1325, ssd1331, sh1106
from time import sleep
from PIL import Image



serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, rotate=0)

displayMessage="Hello!"
with canvas(device) as draw:
    draw.rectangle(device.bounding_box, outline="white", fill="black")
    text_width, text_height = draw.textsize(displayMessage)
    x = (device.width - text_width) / 2
    y = (device.height - text_height) / 2
    draw.text((x, y), displayMessage, fill="white")

usb_config_path = "/media/pi/CONFIGDRIVE/config.json"
# Read configuration variables from a JSON file   
try:
    # Load configuration variables from the disk
    with open('config.json') as config_file:
        config = json.load(config_file)
        # Set the initial last modified timestamp
        config['last_modified'] = os.path.getmtime('config.json')

    # Check if the file has been modified since last read
    if os.path.getmtime(usb_config_path) > config['last_modified']:
        with open(usb_config_path) as config_file:
            config = json.load(config_file)
            # Update the last modified timestamp
            config['last_modified'] = os.path.getmtime(usb_config_path)
except FileNotFoundError:
    # Load configuration variables from the disk
    with open('config.json') as config_file:
        config = json.load(config_file)
        # Set the initial last modified timestamp
        config['last_modified'] = os.path.getmtime('config.json')


# Use variables in the script
api_key = config['openai_api_key']
telegram_bot_token = config['telegram_bot_token']
bot = telepot.Bot(telegram_bot_token)
inline_keyboard_labels = config['inline_keyboard_labels']
default_prompt = config['default_prompt']
prompts = config['prompts']

# Declare payload as a global variable
payload = None

# Set up headers for OpenAI API
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

# Define the path for the lock file
lock_file_path = '/tmp/bot_lock'

# Create an instance of Picamera2
picam2 = Picamera2()
camera_config = picam2.create_preview_configuration()

# Function to remove the lock file
def remove_lock_file():
    print('Removing lock file...')
    if os.path.exists(lock_file_path):
        os.remove(lock_file_path)

# Signal handler for graceful exit
def signal_handler(sig, frame):
    print('Exiting...')
    remove_lock_file()
    sys.exit(0)

# Associate signal handler with the interrupt signal
signal.signal(signal.SIGINT, signal_handler)

# Check if another instance is already running
if os.path.exists(lock_file_path):
    print('Another instance is already running. Exiting...')
    sys.exit(1)

# Create a lock file
open(lock_file_path, 'w').close()

# Message handler function
def handle(msg):
    global payload  # Make payload a global variable
    chat_id = msg['chat']['id']
    command = msg['text']

    print('Got command: {}'.format(command))

    if command == '/take_a_photo':
        print('Wait! I will take a photo...')
        
        displayMessage="Wait! I will take a photo"
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            text_lines = textwrap.wrap(displayMessage, width=16)  # Adjust the width as needed
            y = 15
            for line in text_lines:
                text_width, text_height = draw.textsize(line)  # Fix the indentation here
                x = (device.width - text_width) / 2
                draw.text((x, y), line, fill="white")
                y += text_height

        bot.sendMessage(chat_id, 'Wait! Now I will take a photo.')
        picam2.configure(camera_config)
        picam2.start()
        time.sleep(2)
        picam2.capture_file("test-1.jpg")
        # Generate PDF with the inserted file
        
        picam2.stop()

        # Function to encode the image
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

        # Path to your image
        image_path = "test-1.jpg"

        # Getting the base64 string
        base64_image = encode_image(image_path)
        # Apri l'immagine
        image_path = "test-1.jpg"
        image = Image.open(image_path)

        # Ruota l'immagine di 90 gradi in senso orario
        rotated_image = image.rotate(90, expand=True)

        # Salva l'immagine ruotata temporaneamente
        rotated_image_path = "rotated_image.jpg"
        rotated_image.save(rotated_image_path)

                    
        with open(rotated_image_path, "rb") as photo_file:
            bot.sendPhoto(chat_id, photo_file)
        os.remove(rotated_image_path)

        # Create inline keyboard with labels
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f'/button{i+1}')] for i, label in enumerate(inline_keyboard_labels)
        ])

        # Send 'Choose a judge:' message with inline keyboard
        bot.sendMessage(chat_id, 'Choose a judge:', reply_markup=inline_keyboard)
        displayMessage="Choose a judge"
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            text_lines = textwrap.wrap(displayMessage, width=16)  # Adjust the width as needed
            y = 15
            for line in text_lines:
                text_width, text_height = draw.textsize(line)  # Fix the indentation here
                x = (device.width - text_width) / 2
                draw.text((x, y), line, fill="white")
                y += text_height

        # Create payload with necessary data
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

    elif command == '/time':
        bot.sendMessage(chat_id, str(datetime.datetime.now()))

    elif command == '/start':
        displayMessage="Hello!"
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            text_width, text_height = draw.textsize(displayMessage)
            x = (device.width - text_width) / 2
            y = (device.height - text_height) / 2
            draw.text((x, y), displayMessage, fill="white")
    
        # Create an inline response with bot instructions
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Take a Photo', callback_data='/take_a_photo')],
        ])

        bot.sendMessage(chat_id, 'Welcome to the Bot!\n\nTo take a photo, use the command /take_a_photo.')

def move_and_remove_image(image_path, pdf_path):
    current_time = datetime.datetime.now()
    timestamp = current_time.strftime("%Y%m%d_%H%M%S")  # Format current time as string
    new_folder_path = f"/home/pi/Pictures/{timestamp}"  # Replace with desired path

    # Create the new folder if it doesn't already exist
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)

    # Construct the new path for the moved file
    new_image_path = os.path.join(new_folder_path, f"test-1_{timestamp}.jpg")
    new_pdf_path = os.path.join(new_folder_path, f"output1_{timestamp}.pdf")

    # Move the file to the new folder
    shutil.move(image_path, new_image_path)
    shutil.move(pdf_path, new_pdf_path)
        
def on_callback_query(msg):
    global payload
    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')    

    if query_data.startswith('/button'):
        # Extract the prompt corresponding to the button command
        button_index = int(query_data[-1]) - 1  # Subtract 1 as array indices start from 0
        if 0 <= button_index < len(prompts):
            label = prompts[button_index]
        else:
            label = "Label not found."

        # Modify the payload with the current prompt
        prompt = f"{label}"
        payload['messages'][0]['content'][0]['text'] = prompt

        # Send the request to OpenAI
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        json_data = response.json()

        content_message = json_data['choices'][0]['message']['content']

        print(content_message)
        
        # Print the image on CUPS lp
        os.system('lpr -U pi test-1.jpg')
    
        displayMessage="Photo captured successfully!"
        
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            text_lines = textwrap.wrap(displayMessage, width=16)  # Adjust the width as needed
            y = 15
            for line in text_lines:
                text_width, text_height = draw.textsize(line)  # Fix the indentation here
                x = (device.width - text_width) / 2
                draw.text((x, y), line, fill="white")
                y += text_height
        print("Photo captured successfully!")

        displayMessage="I'm printing out the magic!"
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            text_lines = textwrap.wrap(displayMessage, width=16)  # Adjust the width as needed
            y = 15
            for line in text_lines:
                text_width, text_height = draw.textsize(line)  # Fix the indentation here
                x = (device.width - text_width) / 2
                draw.text((x, y), line, fill="white")
                y += text_height


        
    # def print_text_on_cups(text):
        # Set the name of your CUPS printer
        printer_name = "nt1809"
        pdf_path = "/tmp/output1.pdf"  # Replace with desired output path
        custom_css_path = "custom.css"


        # Convert text to HTML
        html_content = f"<html><head><meta charset='UTF-8'></head><body><hr>{content_message}</body><hr></html>"
        options = {
            'page-size': 'Letter',
            'orientation': 'portrait',
            'margin-top': '0.75in',
            'margin-right': '0.25in',
            'margin-bottom': '0.25in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'user-style-sheet': custom_css_path  # Use custom CSS file


        }

        # Convert HTML to PDF
        pdfkit.from_string(html_content, pdf_path, options=options)

        # Command to send the print file to CUPS
        cups_command = f"lp -d {printer_name} {pdf_path}"

        # # Execute the command
        subprocess.run(cups_command, shell=True)

        # move to new folder and remove the image and text
        move_and_remove_image("test-1.jpg","/tmp/output1.pdf")
        

# Register the command and callback data handling functions
MessageLoop(bot, {'chat': handle, 'callback_query': on_callback_query}).run_as_thread()
print('I am listening ...')
displayMessage="I am listening ..."
# Box and text rendered in portrait mode


# Main loop to keep the script running
try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    pass
finally:
    # Clean up and exit
    remove_lock_file()
    sys.exit(0)
