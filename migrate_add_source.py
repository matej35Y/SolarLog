#!/usr/bin/env python3
"""
Migration script to add 'source' field to existing HourlyPrice records
Sets all existing records to 'hupx' as default
"""
import sys
sys.path.append('.')

from app.models import HourlyPrice, session, engine
from sqlalchemy import text

def migrate_database():
    print("🔄 Starting database migration...")
    print("=" * 50)
    
    try:
        # Check if source column exists
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(hourly_prices)"))
            columns = [row[1] for row in result]
            
            if 'source' in columns:
                print("✅ Source column already exists")
            else:
                print("📝 Adding source column...")
                # Add source column with default value
                conn.execute(text("ALTER TABLE hourly_prices ADD COLUMN source VARCHAR DEFAULT 'hupx'"))
                conn.commit()
                print("✅ Source column added")
            
            # Update existing records without source to 'hupx'
            result = conn.execute(text("UPDATE hourly_prices SET source = 'hupx' WHERE source IS NULL"))
            conn.commit()
            updated = result.rowcount
            print(f"✅ Updated {updated} existing records with source='hupx'")
        
        # Recreate the table with unique constraint if needed
        print("\n📝 Checking unique constraint...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='hourly_prices'"))
            table_sql = result.fetchone()
            if table_sql and '_date_hour_source_uc' not in table_sql[0]:
                print("⚠️  Unique constraint needs to be updated manually")
                print("   The new constraint includes 'source' field")
                print("   You may need to recreate the table or add the constraint manually")
        
        print("\n" + "=" * 50)
        print("✅ Migration completed successfully!")
        print("\nNote: If you encounter unique constraint errors, you may need to:")
        print("1. Drop and recreate the table, OR")
        print("2. Manually add the unique constraint: _date_hour_source_uc")
        
    except Exception as e:
        print(f"\n❌ Error during migration: {str(e)}")
        session.rollback()
        raise

if __name__ == "__main__":
    migrate_database()
