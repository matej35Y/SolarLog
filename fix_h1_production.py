import sqlite3
import os

def fix_database():
    db_path = 'hupx_prices.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check existing H1 records
        cursor.execute("SELECT COUNT(*) FROM energy_generation WHERE hour = 'H1' AND energy_kwh > 1.0")
        big_h1_count = cursor.fetchone()[0]
        
        print(f"Found {big_h1_count} H1 records with energy > 1 kWh (likely erroneous spikes).")

        if big_h1_count > 0:
            # Update all H1 records to 0.0
            cursor.execute("UPDATE energy_generation SET energy_kwh = 0.0 WHERE hour = 'H1'")
            print(f"Updated all records for hour 'H1' to 0.0 kWh.")
            conn.commit()
        else:
            print("No significant H1 spikes found (records might have been very small or already 0).")

        conn.close()
        print("Done.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_database()
