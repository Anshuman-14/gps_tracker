import sqlite3
import pandas as pd
import os
from datetime import datetime
import time

DB_NAME = "location.db"

def fetch_and_append_locations():
    with sqlite3.connect(DB_NAME) as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM current_location")
        rows = cur.fetchall()

    headers = ['device_id', 'name', 'latitude', 'longitude', 'nearest_landmark', 'battery', 'timestamp']

    for row in rows:
        device_id = row[0]
        file_name = f"{device_id}.xlsx"
        df_new = pd.DataFrame([row], columns=headers)

        if os.path.exists(file_name):
            existing_df = pd.read_excel(file_name)
            updated_df = pd.concat([existing_df, df_new], ignore_index=True)
        else:
            updated_df = df_new

        updated_df.to_excel(file_name, index=False)
        print(f"Appended location for {device_id} to {file_name}")

if __name__ == "__main__":
    print("Starting location export every 15 minutes.")
    while True:
        fetch_and_append_locations()
        print(f"Waiting 15 minutes... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        time.sleep(15 * 60)
