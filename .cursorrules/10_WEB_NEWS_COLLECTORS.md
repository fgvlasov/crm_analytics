# 10 — Web / News / Directory Collectors Requirements

## Purpose

The second lead discovery flow monitors public web sources, news sites, directories and thematic platforms to detect commercial signals and create candidate leads.

## Source types

Support these source types:

```text
rss_feed
news_site
company_directory
project_directory
search_query
custom_url_list
```

## Discovery targets

Detect B2B opportunity signals such as:

- factory expansion;
- new production facility;
- new warehouse;
- cold storage project;
- food processing investment;
- logistics center construction;
- public-sector facility modernization;
- hotel/restaurant chain expansion;
- pharma/healthcare cold-chain needs;
- industrial refrigeration upgrade;
- tender announcement;
- construction permit / project listing.

For other tenants, these signals must be configurable by industry.

## Source configuration

Fields:

```text
name
source_type
base_url or query
country
language
positive_keywords
negative_keywords
allowed_domains
excluded_domains
schedule
max_pages_per_run
max_depth
respect_robots_txt bool default true
```

## Crawling rules

- Respect robots.txt where applicable.
- Use reasonable rate limits.
- Do not bypass paywalls or authentication.
- Store raw evidence where allowed.
- Use canonical URL normalization.
- Avoid crawling entire websites without explicit configuration.

## Generic RSS flow

```text
Fetch RSS
    ↓
Parse entries
    ↓
Normalize URL/title/date/summary
    ↓
Fetch article page if allowed
    ↓
Extract text
    ↓
AI signal detection
    ↓
Candidate lead if relevant
```

## Generic news URL flow

```text
Fetch configured page
    ↓
Extract article links
    ↓
Filter by keywords/date
    ↓
Fetch detail pages
    ↓
Extract text
    ↓
Normalize SourceItem
    ↓
AI signal detection
```

## Search query flow

Use this carefully.

Possible providers:

- commercial search API;
- customer-configured search provider;
- manual URL list.

Do not scrape search engine result pages directly unless compliant with terms.

## Text extraction

Use layered extraction:

1. structured metadata: OpenGraph, schema.org;
2. article extraction library;
3. DOM heuristics;
4. fallback to visible text.

Keep:

```text
title
description
published date
author/source
main text
canonical url
language
```

## AI signal detection schema

AI must return:

```json
{
  "is_commercial_signal": true,
  "signal_type": "factory_expansion",
  "relevance_score": 0,
  "confidence": 0,
  "company_name": "...",
  "project_location": "...",
  "project_summary": "...",
  "why_relevant": "...",
  "missing_information": ["..."],
  "recommended_action": "...",
  "evidence_quotes": [
    {
      "text": "short excerpt",
      "source_url": "https://..."
    }
  ]
}
```

## Candidate generation

Create candidate if:

- `is_commercial_signal = true`;
- score >= threshold;
- not duplicate;
- source confidence acceptable.

Candidate name format:

```text
{Signal Type}: {Company Name} — {short project summary}
```

## Deduplication

Deduplicate by:

- canonical URL hash;
- company + signal type + project location;
- content similarity;
- same article syndicated across domains.

## Source evidence

Every candidate must retain:

- source URL;
- source title;
- published date if available;
- extracted excerpt;
- source item ID;
- crawl timestamp;
- confidence.

## Tenant-specific industry profile

Each tenant should define:

```text
business_description
target_industries
target_project_types
positive_keywords
negative_keywords
geographic_scope
minimum_project_size
```

Coldex sample profile:

```text
Industrial refrigeration, cold rooms, freezer rooms, freezer warehouses,
cold-chain logistics, food processing, industrial cooling systems,
reconstruction and modernization of refrigeration systems.
```

## Human review

All web-discovered leads should be reviewed before pushing to Odoo.

No automatic Odoo creation for public-web candidates in MVP unless tenant explicitly enables it.

## Acceptance criteria

- User can create RSS/news/custom URL source.
- Source run creates SourceItems.
- AI detects at least one commercial signal from test page.
- Candidate has evidence and source link.
- Duplicates are suppressed.
- User can approve and push candidate to Odoo.
- Respect plan limits and source rate limits.
