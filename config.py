import os
from dotenv import load_dotenv

load_dotenv('config/.env')

DATABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
