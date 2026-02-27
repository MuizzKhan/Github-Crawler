import os
import requests
import psycopg2
from datetime import datetime

# GitHub GraphQL endpoint
GITHUB_API_URL = "https://api.github.com/graphql"

# Use the default GitHub Actions token (automatically available in workflows)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Database connection settings (match your workflow env)
DB_HOST = "localhost"
DB_NAME = "github_data"
DB_USER = "postgres"
DB_PASSWORD = "postgres"

# GraphQL query to fetch repositories (example: search by stars)
query = """
query($cursor: String) {
  search(query: "stars:>100", type: REPOSITORY, first: 100, after: $cursor) {
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

def fetch_repos():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    cursor = None
    repos = []

    while len(repos) < 100000:
        variables = {"cursor": cursor}
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
    repos = fetch_repos()
    print(f"Fetched {len(repos)} repositories")
    save_to_db(repos)
