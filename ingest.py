import os
import logging
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

def ingest_clients(file_path):
    try:
        df = pd.read_csv(file_path).drop_duplicates(subset=['email']).dropna(subset=['id', 'email', 'username'])
        for _, row in df.iterrows():
            supabase.table("clients").upsert({
                "id": row['id'], 
                "username": row['username'], 
                "email": row['email'],
                "role": row.get('role', 'creator'), 
                "status": "active"
            }).execute()
        logging.info("Ingesta finalizada con éxito.")
    except Exception as e:
        logging.error(f"Error crítico: {e}")

if __name__ == "__main__":
    ingest_clients('cartera_diego.csv')
