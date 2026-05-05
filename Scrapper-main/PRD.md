# SDR Contact Scraper — Product Requirements

## What This Is

A tool that finds tech startup decision-makers and collects their contact information for outreach. It scrapes public sources for companies and people, then enriches the results with LinkedIn URLs and work emails.

The output is a spreadsheet with rows like:

| Company | Person | Title | LinkedIn | Email |
|---------|--------|-------|----------|-------|
| Acme AI | Jane Smith | Co-Founder & CEO | linkedin.com/in/janesmith | jane@acme.ai |

---

## Why We Need This

Finding the right person to reach out to at a startup is tedious. You search YC, browse company websites, cross-reference LinkedIn, guess email patterns — and repeat hundreds of times.

This tool automates that cycle: discover companies, find their founders and leaders, get contact info, export a clean list.

---

## Who This Is For

Anyone doing outbound research — founders, SDRs, or operators who need a pipeline of decision-maker contacts at tech startups.

---

## What We Want

| Goal | Target |
|------|--------|
| New contacts per month | 1,000+ |
| Contacts with LinkedIn URL | 60%+ |
| Contacts with work email | 40%+ |
| Monthly cost for paid tools | Under $200 |
| Time to first usable export | Days, not weeks |

---

## How It Works

### Step 1: Find companies

Scrape public directories of tech startups. Starting sources:

- **Y Combinator directory** — ~5,000 companies with founder details on each page
- **Product Hunt** — daily new product launches with maker profiles
- **Company websites** — team/about pages for additional people

These are free. No API keys or paid accounts needed.

### Step 2: Find people at those companies

For each company, extract the people who matter:

- Founders and co-founders
- C-suite (CEO, CTO, COO)
- VPs, Heads, Directors

The tool pulls names, titles, and any LinkedIn or Twitter links that appear on the source page.

### Step 3: Enrich with emails and missing LinkedIn URLs

Use free-tier enrichment services to fill gaps:

- **Apollo.io** (free tier, ~10,000 credits/month) — given a name and company domain, returns their work email and LinkedIn URL
- **Hunter.io** (free tier, 25 lookups + 50 verifications/month) — backup email finder and verifier

Paid enrichment only runs on people we already discovered for free. We never pay to find people — only to fill in their contact details.

### Step 4: Export

Export filtered results as CSV or Excel. Filter by:

- Has LinkedIn URL
- Has work email
- Title/seniority (e.g. only founders)
- Company source (e.g. only YC companies)

---

## What We Are Not Building

- A cold email sending tool — this is research and list-building only
- A LinkedIn scraper — we never scrape LinkedIn directly
- A CRM — export the list and use it wherever you want
- A fully automated system — you run commands, review results, then export

---

## Data Sources

### Free sources (no signup needed)

| Source | What it gives us | Volume |
|--------|-----------------|--------|
| YC Directory | Companies + founder names + LinkedIn URLs + Twitter | ~5,000 companies, ~10,000 founders |
| Product Hunt | New product launches + maker profiles | Hundreds per month |
| Company team pages | Additional team members at discovered companies | Variable (~20-40% success rate) |

### Enrichment services (free tiers)

| Service | What it gives us | Free tier |
|---------|-----------------|-----------|
| Apollo.io | Work email + LinkedIn URL from name + domain | ~10,000 credits/month |
| Hunter.io | Email lookup + email verification | 25 searches + 50 verifications/month |

### Future sources (not in V1)

These can be added later without rebuilding anything:

- Crunchbase (funded company data)
- GitHub (technical founders via popular repos)
- Wellfound/AngelList (startup job boards)
- Proxycurl (LinkedIn profile enrichment)
- Any CSV import or manual list

---

## Volume Math

Can we actually hit 1,000 contacts per month?

- YC has ~5,000 companies with ~2 founders each = ~10,000 potential contacts in the backlog
- Scraping 500 companies per month = ~1,000 founders
- Product Hunt adds breadth beyond YC
- Apollo free tier can enrich up to 10,000 records per month

The volume target is achievable with YC alone. Product Hunt and team pages add diversity.

---

## Budget

### V1 cost: $0/month

All V1 sources and enrichment services have free tiers. No credit card needed to start.

### If we outgrow free tiers

| Upgrade | Cost | When to consider |
|---------|------|-----------------|
| Apollo paid tier | ~$49/month | If free credits run out before hitting monthly target |
| Hunter Growth | ~$149/month | If we need high-volume email verification |
| Proxycurl | ~$49/month | If LinkedIn coverage is below 60% after Apollo enrichment |

Maximum realistic spend: ~$200/month, only if free tiers are insufficient.

---

## What a Contact Record Looks Like

Every contact in the database has:

| Field | Example | Required? |
|-------|---------|-----------|
| Company name | Stripe | Yes |
| Company domain | stripe.com | Yes |
| Company website | https://stripe.com | No |
| Person name | Patrick Collison | Yes |
| Title | Co-Founder & CEO | Yes |
| Seniority | Founder | Auto-detected |
| LinkedIn URL | linkedin.com/in/patrickcollison | Goal: 60%+ |
| Twitter/X URL | x.com/patrickc | When available |
| Work email | patrick@stripe.com | Goal: 40%+ |
| Email status | Verified | When checked |
| Source | YC | Always tracked |

---

## Rollout Phases

### Phase 1: YC scraper + export

- Scrape YC directory for companies and founders
- Store in local database (no server setup needed)
- Export to CSV
- **Result:** first usable contact list within days

### Phase 2: More sources + email enrichment

- Add Product Hunt scraping
- Add company team page crawling
- Connect Apollo.io for email + LinkedIn enrichment
- Connect Hunter.io as backup
- **Result:** multi-source contact list with emails

### Phase 3: Polish

- Search and filter contacts from the command line
- Excel export with formatting
- Status dashboard showing coverage percentages
- Deduplication improvements
- **Result:** repeatable monthly workflow

---

## Risks

| Risk | Likelihood | What happens | Backup plan |
|------|-----------|--------------|-------------|
| YC website changes layout | Medium | Founder scraping breaks temporarily | Fix the scraper; company data still comes from their API |
| Apollo changes free tier | Medium | Primary email source gone | Hunter backup; Apollo paid ($49/mo) fits budget |
| Product Hunt blocks us | High | One source lost (not critical) | YC alone covers volume target |
| Team page crawler works poorly | Expected | Low yield from this source | Apollo enrichment compensates |
| Not enough contacts per month | Low | Volume target missed | YC backlog has 10,000+ potential contacts |

---

## How We'll Know It's Working

After Phase 1:
- Can export a CSV with 50+ companies and their founders
- At least some founders have LinkedIn URLs from YC pages

After Phase 2:
- 60%+ of contacts have a LinkedIn URL (from scraping + Apollo)
- 40%+ of contacts have a work email (from Apollo + Hunter)
- Multiple sources contributing contacts

After Phase 3:
- Can run a monthly batch and export 1,000+ filtered contacts
- Status command shows coverage percentages and source breakdown
- Total monthly spend stays under $200

---

## Guiding Principles

1. **Get contacts fast, polish later** — a working scraper beats a perfect architecture
2. **Free before paid** — never pay to discover people; only pay to fill in missing contact details
3. **Both LinkedIn and email matter** — multi-channel outreach needs both
4. **Track where data came from** — every record knows its source
5. **Easy to add new sources** — each scraper is independent; adding one doesn't break others
6. **No LinkedIn scraping** — use public directories and enrichment APIs instead



----- 
well found

maximum data
