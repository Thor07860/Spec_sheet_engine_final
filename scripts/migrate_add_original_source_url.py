#!/usr/bin/env python
"""
Migration script to add original_source_url column to equipment table
Handles the schema change from single source_url to dual-URL tracking
"""

from sqlalchemy import text
from app.core.database import engine

def migrate():
    """Add original_source_url column to equipment table if it doesn't exist"""
    
    with engine.begin() as conn:
        # Check if the column already exists
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='equipment' AND column_name='original_source_url'
            )
            """)
        )
        
        column_exists = result.scalar()
        
        if column_exists:
            print("✅ Column 'original_source_url' already exists in equipment table")
            return
        
        # Add the column if it doesn't exist
        print("🔧 Adding 'original_source_url' column to equipment table...")
        conn.execute(
            text("""
            ALTER TABLE equipment 
            ADD COLUMN original_source_url TEXT NULL
            """)
        )
        print("✅ Successfully added 'original_source_url' column")
        
        # Also verify source_url exists (just in case)
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='equipment' AND column_name='source_url'
            )
            """)
        )
        
        if result.scalar():
            print("✅ 'source_url' column already exists")
        else:
            print("⚠️  'source_url' column not found - you may need to investigate")

if __name__ == "__main__":
    try:
        migrate()
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
