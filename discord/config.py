import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
print("TOKEN kebaca:", TOKEN is not None)  # <-- tambah ini buat tes

