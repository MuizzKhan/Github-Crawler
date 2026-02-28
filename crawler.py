import os
import requests
import psycopg2
from datetime import datetime
import time

# GitHub GraphQL endpoint
GITHUB_API_URL = "https://api.github.com/graphql"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Database connection settings
DB_HOST = "localhost"
DB_NAME = "github_data"
DB_USER = "postgres"
DB_PASSWORD = "postgres"

# GraphQL query template
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

def fetch_repos_for_range(range_query, max_needed, total_count):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    cursor = None
    repos = []

    while True:
        variables = {"cursor": cursor, "range": range_query}
        response = requests.post(GITHUB_API_URL, json={"query": query, "variables": variables}, headers=headers)

        # Handle non-200 responses
        if response.status_code != 200:
            print(f"Request failed with status {response.status_code}: {response.text}")
            time.sleep(60)
            continue

        # Handle rate limits
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        if remaining == 0:
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()+60))
            sleep_for = reset_time - int(time.time())
            print(f"Rate limit hit. Sleeping for {sleep_for} seconds...")
            time.sleep(max(sleep_for, 60))
            continue

        # Safely decode JSON
        try:
            data = response.json()
        except Exception as e:
            print("Failed to decode JSON:", e)
            print("Response text:", response.text)
            time.sleep(60)
            continue

        if "errors" in data:
            print("Error:", data["errors"])
            time.sleep(30)
            continue

        search = data["data"]["search"]

        for repo in search["nodes"]:
            repos.append(repo)
            total_count += 1
            if total_count >= max_needed:
                return repos, total_count

        if not search["pageInfo"]["hasNextPage"]:
            break

        cursor = search["pageInfo"]["endCursor"]

        # Small delay to avoid hammering API
        time.sleep(1)

    return repos, total_count

def save_to_db(repos):
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()

    for repo in repos:
        cur.execute("""
            INSERT INTO repositories (name, stars, last_updated)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET stars = EXCLUDED.stars,
                last_updated = EXCLUDED.last_updated;
        """, (repo["nameWithOwner"], repo["stargazerCount"], datetime.utcnow()))

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    # Generate fine-grained ranges for small repos
    star_ranges = []
    for i in range(0, 500, 2):  # buckets of 2 stars each
        star_ranges.append(f"stars:{i}..{i+1}")
    for i in range(500, 1000, 5):  # buckets of 5 stars each
        star_ranges.append(f"stars:{i}..{i+4}")
    # Larger ranges for big repos
    star_ranges += [
        "stars:1000..5000",
        "stars:5001..10000",
        "stars:10001..50000",
        "stars:50001..100000",
        "stars:>100000"
    ]

    total_count = 0
    max_needed = 100000

    for r in star_ranges:
        if total_count >= max_needed:
            break
        print(f"Fetching repos for range {r}...")
        repos, total_count = fetch_repos_for_range(r, max_needed, total_count)
        print(f"Fetched {len(repos)} repos for {r} (total so far: {total_count})")
        save_to_db(repos)

    print(f"✅ Finished. Total repos fetched: {total_count}")
