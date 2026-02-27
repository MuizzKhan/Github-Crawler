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

def fetch_repos_for_range(range_query):
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

        if not search["pageInfo"]["hasNextPage"]:
            break

        cursor = search["pageInfo"]["endCursor"]

        # Respect rate limits
        time.sleep(1)

    return repos

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
    # Define star ranges to bypass 1000 cap
    star_ranges = [
        "stars:0..10",
        "stars:11..50",
        "stars:51..100",
        "stars:101..500",
        "stars:501..1000",
        "stars:1001..5000",
        "stars:>5000"
    ]

    total_repos = []
    for r in star_ranges:
        print(f"Fetching repos for range {r}...")
        repos = fetch_repos_for_range(r)
        print(f"Fetched {len(repos)} repos for {r}")
        save_to_db(repos)
        total_repos.extend(repos)

    print(f"Total repos fetched: {len(total_repos)}")
