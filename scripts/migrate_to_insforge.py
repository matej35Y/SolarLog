import sqlite3
import uuid
from datetime import datetime

# Connect to local SQLite database
conn = sqlite3.connect('hupx_prices.db')
cursor = conn.cursor()

# Export data to a Postgres-compatible SQL script
with open('backup_for_insforge.sql', 'w') as f:
    f.write('BEGIN;\n\n')
    
    # 1. Export hourly_prices
    cursor.execute('SELECT date, hour, price, source FROM hourly_prices')
    prices = cursor.fetchall()
    
    if prices:
        f.write('INSERT INTO hourly_prices (id, date, hour, price, source) VALUES\n')
        values_list = []
        for row in prices:
            date_val, hour_val, price_val, source_val = row
            # generate UUID
            uid = str(uuid.uuid4())
            # Format row: ('uuid', '2023-01-01', 'H1', 123.45, 'hupx')
            values_list.append(f"('{uid}', '{date_val}', '{hour_val}', {price_val}, '{source_val}')")
            
        f.write(',\n'.join(values_list))
        f.write(' ON CONFLICT (date, hour, source) DO NOTHING;\n\n')
        print(f"Exported {len(prices)} hourly_prices records.")

    # 2. Export energy_generation
    cursor.execute('SELECT date, hour, energy_kwh FROM energy_generation')
    energy = cursor.fetchall()

    if energy:
        f.write('INSERT INTO energy_generation (id, date, hour, energy_kwh) VALUES\n')
        values_list = []
        for row in energy:
            date_val, hour_val, energy_val = row
            uid = str(uuid.uuid4())
            values_list.append(f"('{uid}', '{date_val}', '{hour_val}', {energy_val})")
            
        f.write(',\n'.join(values_list))
        f.write(' ON CONFLICT (date, hour) DO NOTHING;\n\n')
        print(f"Exported {len(energy)} energy_generation records.")

    f.write('COMMIT;\n')

print("Export complete. Run 'npx @insforge/cli db import backup_for_insforge.sql' to import to InsForge.")
