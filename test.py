
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

conn = mysql.connector.connect(
    host="chatbotdb.cv0eq40gqpvk.ap-south-1.rds.amazonaws.com",
    user="admin",
    password="ga0NvgNfhX9VzXbMYOeM"
)
cursor = conn.cursor()

# Create the database if it doesn't exist
cursor.execute("CREATE DATABASE IF NOT EXISTS chatbotdb;")
print("Database 'chatbotdb' ensured.")

# Optional: switch to the new database
cursor.execute("USE chatbotdb;")

# You can now create tables, etc.
# Example: cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT PRIMARY KEY, name VARCHAR(50));")

conn.commit()
cursor.close()
conn.close()
