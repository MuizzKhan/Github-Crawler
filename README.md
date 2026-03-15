# GitHub Repository Stars Crawler

## 📌 Overview
This project implements a GitHub Actions workflow that crawls **100,000 GitHub repositories**, collects their star counts, stores the data in a **Postgres database**, and exports the results as a **CSV artifact**.  
It demonstrates automation, clean architecture, and scalability considerations for large‑scale data collection.

---

## ⚙️ Pipeline Explanation
The workflow (`.github/workflows/github-crawler.yml`) defines the following steps:

1. **Trigger**  
   - Runs automatically on push to `main`.  
   - Can also be triggered manually via `workflow_dispatch` in the Actions tab.

2. **Services**  
   - Spins up a **Postgres service container** with user/password `postgres` and database `github_data`.

3. **Setup**  
   - Checks out the repository code.  
   - Installs Python and dependencies (`requests`, `psycopg2-binary`).  
   - Creates the `repositories` table schema in Postgres.

4. **Crawler Execution**  
   - Runs `crawler.py`, which:  
     - Generates star ranges (0–500 in buckets of 2, 500–1000 in buckets of 5, larger ranges beyond).  
     - Calls the GitHub GraphQL API to fetch repositories.  
     - Handles pagination, rate limits, and retries.  
     - Saves results into Postgres using UPSERT logic.

5. **Export & Artifact Upload**  
   - Dumps the `repositories` table into `repos.csv`.  
   - Uploads the file as an artifact using `actions/upload-artifact@v4`.

---

## ▶️ How to Run
### Option 1: Automatic
- Push changes to the `main` branch.  
- Workflow runs automatically.

### Option 2: Manual
- Go to the **Actions tab** in GitHub.  
- Select the workflow named **GitHub Crawler**.  
- Click **Run workflow** to trigger it manually.

---

## 🧪 How to Test This Repository
1. Fork this repository into your own GitHub account.  
2. Navigate to the **Actions tab** in your fork.  
3. Select the workflow **GitHub Crawler**.  
4. Click **Run workflow** to start it.  
5. After the run completes, download the artifact (`repo-stars`) from the Actions summary.  
6. Open `repos.csv` locally to inspect the data.

---

## 📊 Scaling Reflection
If we needed to crawl **500 million repositories** instead of 100,000:
- **Distributed Crawling**: Use multiple workers across regions, each handling a shard of star ranges.  
- **Data Lake Storage**: Store raw data in S3/HDFS instead of Postgres.  
- **Streaming Pipelines**: Use Kafka or similar to handle continuous ingestion.  
- **Batch Processing**: Employ Spark or Flink for large‑scale aggregation.  
- **Monitoring**: Add dashboards for API rate limits, retries, and throughput.

---

## 🗄️ Schema Evolution
Currently, the schema is:

```sql
CREATE TABLE repositories (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  stars INT NOT NULL,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

To evolve this schema for richer GitHub metadata, we would add normalized tables for each entity:

- Issues Table  
Tracks issues per repository, with state transitions.
CREATE TABLE issues (
  id SERIAL PRIMARY KEY,
  repo_id INT REFERENCES repositories(id),
  issue_number INT NOT NULL,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL,
  closed_at TIMESTAMP
);

- Pull Requests Table  
Captures PR lifecycle and merge events.
CREATE TABLE pull_requests (
  id SERIAL PRIMARY KEY,
  repo_id INT REFERENCES repositories(id),
  pr_number INT NOT NULL,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  merged_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL
);

- Comments Table  
Stores user comments on issues/PRs.
CREATE TABLE comments (
  id SERIAL PRIMARY KEY,
  repo_id INT REFERENCES repositories(id),
  comment_id INT NOT NULL,
  body TEXT NOT NULL,
  author TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

- Reviews Table  
Represents code reviews and their outcomes.
CREATE TABLE reviews (
  id SERIAL PRIMARY KEY,
  repo_id INT REFERENCES repositories(id),
  review_id INT NOT NULL,
  state TEXT NOT NULL,
  submitted_at TIMESTAMP NOT NULL
);

- CI Checks Table  
Tracks automated CI/CD checks for repositories.
CREATE TABLE ci_checks (
  id SERIAL PRIMARY KEY,
  repo_id INT REFERENCES repositories(id),
  check_id INT NOT NULL,
  status TEXT NOT NULL,
  conclusion TEXT,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP
);
```

## 🏗️ Engineering Practices
This project demonstrates several key engineering principles:

1. **Separation of Concerns**
   - api_client.py: Handles GitHub API calls, pagination, and rate limits.
   - db.py: Manages database connections and UPSERT logic.
   - crawler.py: Orchestrates star ranges and workflow execution.
   - Each module has a single responsibility, making the system easier to maintain.
     
2. **Immutability**
   - Treats fetched data as immutable snapshots.
   - Updates are applied via UPSERT, ensuring rows are replaced atomically without side effects.
  
3. **Anti‑Corruption Layer**
   - GitHub API responses are transformed into internal structures before insertion.
   - Prevents external API quirks from leaking into the database schema.

4. **Clean Architecture**
   - Core logic (crawler orchestration) is independent of infrastructure (Postgres, GitHub API).
   - Infrastructure is injected at runtime, making the system testable and extensible.
   - Clear boundaries between modules improve readability and scalability.

5. **Resilience**
   - Handles API rate limits gracefully with retries and backoff.
   - Catches JSON decoding errors and GraphQL errors, ensuring the crawler doesn’t crash.
  
6. **Scalability Awareness**
   - Uses star ranges to bypass GitHub’s 1000‑item search cap.
   - Modular design allows for distributed crawling if scaled to millions of repositories.
