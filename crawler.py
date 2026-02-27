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
        data = response.json()

        if "errors" in data:
            print("Error:", data["errors"])
            break

        search = data["data"]["search"]

        for repo in search["nodes"]:
            repos.append(repo)
            total_count += 1
            if total_count >= max_needed:
                return repos, total_count

        if not search["pageInfo"]["hasNextPage"]:
            break

        cursor = search["pageInfo"]["endCursor"]

        # Respect rate limits
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
    # Automatically generate ranges
    star_ranges = []
    # Fine-grained ranges for small repos
    for i in range(0, 1000, 10):
        star_ranges.append(f"stars:{i}..{i+9}")
    # Larger ranges for big repos
    star_ranges += [
        "stars:1000..5000",
        "stars:5001..10000",
        "stars:10001..50000",
        "stars:50001..100000",
        "stars:>100000"
    ]

    total_repos = []
    total_count = 0
    max_needed = 100000

    for r in star_ranges:
        if total_count >= max_needed:
            break
        print(f"Fetching repos for range {r}...")
        repos, total_count = fetch_repos_for_range(r, max_needed, total_count)
        print(f"Fetched {len(repos)} repos for {r} (total so far: {total_count})")
        save_to_db(repos)
        total_repos.extend(repos)

    print(f"✅ Finished. Total repos fetched: {len(total_repos)}")
