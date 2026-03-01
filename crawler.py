# Purpose: This is the orchestrator script that coordinates the crawling process.
# Responsibilities:
# - Generate star ranges (merged from ranges.py)
# - Call the API client to fetch repositories for each range
# - Save results into Postgres using db.py
# - Ensure the process stops once 100,000 repositories are collected

# Import fetch_repos_for_range function from api_client module
from api_client import fetch_repos_for_range
# Import save_to_db function from db module
from db import save_to_db

# Function to generate star ranges (merged from ranges.py)
def generate_star_ranges():
    # Initialize list of ranges
    star_ranges = []
    # Fine-grained ranges for small repos (0–500 stars, buckets of 2)
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
    # Return the complete list of ranges
    return star_ranges

# Main execution block
if __name__ == "__main__":
    # Generate star ranges
    star_ranges = generate_star_ranges()
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
        # Fetch repos for this range using API client
        repos, total_count = fetch_repos_for_range(r, max_needed, total_count)
        # Print how many repos were fetched in this range and total so far
        print(f"Fetched {len(repos)} repos for {r} (total so far: {total_count})")
        # Save fetched repos into Postgres database
        save_to_db(repos)

    # Print final message once target is reached or ranges exhausted
    print(f"✅ Finished. Total repos fetched: {total_count}")
