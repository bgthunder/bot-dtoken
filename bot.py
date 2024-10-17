import telebot
import random
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv
import os
import logging
from time import time

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Initialize bot with the token
bot = telebot.TeleBot(BOT_TOKEN)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up connection pooling
dbconfig = {
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME
}
connection_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **dbconfig)

# Rate limiting
user_last_interaction = {}

# Function to connect to the MySQL database using connection pooling
def connect_db():
    return connection_pool.get_connection()

# Function to generate a unique D-Token
def dtoken():
    while True:
        token = random.randint(1000000000, 9999999999)
        if not check_dtoken_exists(token):
            return token

# Function to validate the phone number
def is_valid_phone_number(number):
    return number.isdigit() and len(number) == 10

# Function to check if the phone number already exists in the database
def check_phone_number_exists(phone_number):
    conn = connect_db()
    cursor = conn.cursor()
    query = "SELECT d_token FROM user_data WHERE phone_number = %s"
    cursor.execute(query, (phone_number,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

# Function to check if the D-Token already exists in the database
def check_dtoken_exists(d_token):
    conn = connect_db()
    cursor = conn.cursor()
    query = "SELECT d_token FROM user_data WHERE d_token = %s"
    cursor.execute(query, (d_token,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

# Function to store user data in the database
def store_user_data(username, phone_number, d_token):
    conn = connect_db()
    cursor = conn.cursor()
    query = "INSERT INTO user_data (username, phone_number, d_token) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE d_token=%s"
    cursor.execute(query, (username, phone_number, d_token, d_token))
    conn.commit()
    cursor.close()
    conn.close()

# Function to implement simple rate limiting
def is_rate_limited(user_id):
    current_time = time()
    if user_id in user_last_interaction:
        if current_time - user_last_interaction[user_id] < 5:  # 5 seconds cooldown
            return True
    user_last_interaction[user_id] = current_time
    return False

# Command handler to ask for the user's number
@bot.message_handler(commands=['start'])
def ask_name(message):
    if is_rate_limited(message.from_user.id):
        bot.reply_to(message, "You're sending messages too quickly. Please slow down.")
        logging.warning(f"Rate limit triggered for user {message.from_user.id}")
        return

    bot.reply_to(message, "Hi! Please enter your 10-digit phone number:")

# Message handler to capture user input, validate it, and respond accordingly
@bot.message_handler(func=lambda message: True)
def handle_name(message):
    if is_rate_limited(message.from_user.id):
        bot.reply_to(message, "You're sending messages too quickly. Please slow down.")
        logging.warning(f"Rate limit triggered for user {message.from_user.id}")
        return

    username = message.from_user.username or message.from_user.id  # Use username or ID as fallback
    user_input = message.text.strip()  # Capture the user's input and remove any extra spaces

    # Check if the input is a valid 10-digit phone number
    if is_valid_phone_number(user_input):
        existing_dtoken = check_phone_number_exists(user_input)  # Check if the phone number exists

        if existing_dtoken:
            bot.reply_to(message, f"It is already registered. Your existing D-Token is: {existing_dtoken[0]}")
            logging.info(f"User {username} attempted to register an existing phone number: {user_input}")
        else:
            token = dtoken()  # Generate a new, unique D-Token
            store_user_data(username, user_input, token)  # Store data in the database
            bot.reply_to(message, f"Your D-Token is: {token}")
            logging.info(f"New registration: User {username}, Phone: {user_input}, D-Token: {token}")
    else:
        # If the input is not a valid 10-digit number, ask the user to input it again
        bot.reply_to(message, "Please enter a valid 10-digit phone number.")
        logging.warning(f"Invalid phone number input by user {username}: {user_input}")

# Start polling for new messages
bot.polling()