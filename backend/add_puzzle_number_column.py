"""
Migration script to add puzzle_number column to connections_game table.
Run this once to update the database schema.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL from environment
database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("ERROR: DATABASE_URL not found in environment variables")
    exit(1)

print(f"Connecting to database...")

# Create engine
engine = create_engine(database_url)

# SQL to add the puzzle_number column
add_column_sql = """
ALTER TABLE connections_game
ADD COLUMN IF NOT EXISTS puzzle_number INTEGER;
"""

print("Adding puzzle_number column to connections_game table...")

try:
    with engine.connect() as connection:
        # Execute the SQL
        connection.execute(text(add_column_sql))
        connection.commit()
        print("✓ Successfully added puzzle_number column")

        # Verify the column was added
        result = connection.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'connections_game'
            AND column_name = 'puzzle_number';
        """))

        if result.fetchone():
            print("✓ Column verified in database schema")
        else:
            print("✗ Column not found after addition (this may be normal for some databases)")

except Exception as e:
    print(f"✗ Error adding column: {e}")
    exit(1)

print("\nMigration complete!")
