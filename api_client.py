# Purpose: This module handles all communication with the GitHub GraphQL API.
# It defines the query template and a function to fetch repositories for a given star range.
# Responsibilities:
# - Send requests to GitHub API
# - Handle pagination
# - Respect rate limits
# - Retry on errors
# - Return repository data to the crawler

# Import os to access environment variables (for GitHub token)
import os
# Import requests to make HTTP requests to the GitHub API
import requests
# Import time to add delays for rate limiting and retries
import time

# Define the GitHub GraphQL API endpoint URL
GITHUB_API_URL = "https://api.github.com/graphql"
# Retrieve the GitHub token from environment variables (provided automatically in GitHub Actions)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Define the GraphQL query template
# - Accepts cursor for pagination
# - Accepts star range filter
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
