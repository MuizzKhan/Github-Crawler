# Purpose: This module manages all interactions with the Postgres database.
# Responsibilities:
# - Establish connection to Postgres
# - Insert repository data into the "repositories" table
# - Use UPSERT logic to efficiently update star counts if a repo already exists
# - Ensure data integrity and close connections properly

# Import psycopg2 to connect to and interact with Postgres
import psycopg2
# Import datetime to record when each row was last updated
from datetime import datetime

# Define database connection settings
DB_HOST = "localhost"       # Host where Postgres is running
DB_NAME = "github_data"     # Database name
DB_USER = "postgres"        # Database user
DB_PASSWORD = "postgres"    # Database password

# Function to save a batch of repositories into Postgres
def save_to_db(repos):
    # Connect to Postgres using psycopg2
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    # Create a cursor to execute SQL commands
    cur = conn.cursor()

    # Iterate over each repository in the batch
    for repo in repos:
        # Insert repo into table, update stars if repo already exists (UPSERT)
        cur.execute("""
            INSERT INTO repositories (name, stars, last_updated)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET stars = EXCLUDED.stars,
                last_updated = EXCLUDED.last_updated;
        """, (repo["nameWithOwner"], repo["stargazerCount"], datetime.utcnow()))

    # Commit transaction to save changes
    conn.commit()
    # Close cursor
    cur.close()
    # Close connection
    conn.close()
