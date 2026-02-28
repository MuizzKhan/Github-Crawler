# Import the os module to access environment variables like the GitHub token
import os
# Import requests to make HTTP requests to the GitHub GraphQL API
import requests
# Import psycopg2 to connect to and interact with the Postgres database
import psycopg2
# Import datetime to timestamp when data is inserted or updated
from datetime import datetime
# Import time to add delays for rate limiting and retries
import time

# Define the GitHub GraphQL API endpoint URL
GITHUB_API_URL = "https://api.github.com/graphql"
# Retrieve the GitHub token from environment variables (provided automatically in GitHub Actions)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Define database connection settings for the Postgres service container
DB_HOST = "localhost"       # Host where Postgres is running
DB_NAME = "github_data"     # Database name
DB_USER = "postgres"        # Database user
DB_PASSWORD = "postgres"    # Database password

# Define the GraphQL query template to fetch repositories
# - Accepts a cursor for pagination
# - Accepts a star range filter
# - Returns repository name and star count
query = """
query($cursor: String, $range: String!) {
  search(query: $range, type: REPOSITORY, first: 100, after: $cursor) {
    pageInfo {
      endCursor
      hasNextPage
    }
    nodes {
      ... on Repository {
        nameWithOwner
        stargazerCount
      }
    }
  }
}
"""

# Function to fetch repositories for a given star range
def fetch_repos_for_range(range_query, max_needed, total_count):
    # Set authorization header with GitHub token
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    # Initialize cursor for pagination
    cursor = None
    # Initialize list to store repositories fetched in this range
    repos = []

    # Loop until all pages in this range are fetched or max repos reached
    while True:
        # Define variables for GraphQL query (cursor and star range)
        variables = {"cursor": cursor, "range": range_query}
        # Send POST request to GitHub GraphQL API
        response = requests.post(GITHUB_API_URL, json={"query": query, "variables": variables}, headers=headers)

        # If response status is not 200, print error and retry after delay
        if response.status_code != 200:
            print(f"Request failed with status {response.status_code}: {response.text}")
            time.sleep(60)
            continue

        # Check remaining rate limit from response headers
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        # If rate limit is exhausted, wait until reset time
        if remaining == 0:
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()+60))
            sleep_for = reset_time - int(time.time())
            print(f"Rate limit hit. Sleeping for {sleep_for} seconds...")
            time.sleep(max(sleep_for, 60))
            continue

        # Try to decode JSON response safely
        try:
            data = response.json()
        except Exception as e:
            # If JSON decoding fails, print error and retry after delay
            print("Failed to decode JSON:", e)
            print("Response text:", response.text)
            time.sleep(60)
            continue

        # If GraphQL errors are returned, print them and retry after delay
        if "errors" in data:
            print("Error:", data["errors"])
            time.sleep(30)
            continue

        # Extract search results from response
        search = data["data"]["search"]

        # Iterate over each repository node in the response
        for repo in search["nodes"]:
            # Append repo to list
            repos.append(repo)
            # Increment total count of repos fetched
            total_count += 1
            # If we reached the maximum needed repos, return immediately
            if total_count >= max_needed:
                return repos, total_count

        # If no more pages exist in this range, break out of loop
        if not search["pageInfo"]["hasNextPage"]:
            break

        # Update cursor to fetch next page
        cursor = search["pageInfo"]["endCursor"]

        # Add small delay to avoid hitting API too aggressively
        time.sleep(1)

    # Return repos fetched in this range and updated total count
    return repos, total_count

# Function to save repositories into Postgres database
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

# Main execution block
if __name__ == "__main__":
    # Define star ranges to bypass GitHub's 1000-item search cap
    # Fine-grained ranges for small repos (0–500 stars, buckets of 2)
    star_ranges = []
    for i in range(0, 500, 2):  # Loop from 0 to 500 in steps of 2
        star_ranges.append(f"stars:{i}..{i+1}")  # Add range like "stars:0..1", "stars:2..3", etc.
    # Medium ranges (500–1000 stars, buckets of 5)
    for i in range(500, 1000, 5):  # Loop from 500 to 1000 in steps of 5
        star_ranges.append(f"stars:{i}..{i+4}")  # Add range like "stars:500..504", "stars:505..509", etc.
    # Larger ranges for big repos
    star_ranges += [
        "stars:1000..5000",      # Range for repos with 1000–5000 stars
        "stars:5001..10000",     # Range for repos with 5001–10000 stars
        "stars:10001..50000",    # Range for repos with 10001–50000 stars
        "stars:50001..100000",   # Range for repos with 50001–100000 stars
        "stars:>100000"          # Range for repos with more than 100000 stars
    ]

    # Initialize total count of repos fetched
    total_count = 0
    # Define maximum number of repos to fetch (assignment target = 100,000)
    max_needed = 100000

    # Iterate through each star range until target is reached
    for r in star_ranges:
        # Stop if we already reached the target
        if total_count >= max_needed:
            break
        # Print which range is being fetched
        print(f"Fetching repos for range {r}...")
        # Fetch repos for this range
        repos, total_count = fetch_repos_for_range(r, max_needed, total_count)
        # Print how many repos were fetched in this range and total so far
        print(f"Fetched {len(repos)} repos for {r} (total so far: {total_count})")
        # Save fetched repos into Postgres database
        save_to_db(repos)

    # Print final message once target is reached or ranges exhausted
    print(f"✅ Finished. Total repos fetched: {total_count}")
