# Step 13: Skip Trace Owners

**Script:** `execution/pipeline/skip_trace.py --buybox-id UUID`

## Purpose
Look up contact information (phone numbers, emails, age) for property owners whose parcels have been rated "yes" or "maybe" by the buyer or agent in the map viewer. This is the final step before outreach. Uses the Apify skip-trace actor for batch lookups.

## Input
- Rated parcels from the Django database (Parcel records where `rating` is "yes" or "maybe")
- Owner names and mailing addresses from the Parcel records

## Output
- `Owner` records in the Django database, linked to Parcel via foreign key
- `.tmp/{buyer}/{county}/skip_trace_results.json` (raw API response for debugging)
- Each Owner record contains: phone numbers, email addresses, age, full name

## Process

### 1. Query Rated Parcels
Fetch all Parcel records for the BuyBox where the rating is "yes" or "maybe":
```python
parcels = Parcel.objects.filter(
    buybox_id=buybox_id,
    rating__in=['yes', 'maybe']
)
```

### 2. Deduplicate Owners
Multiple parcels may have the same owner. Group parcels by owner name (normalized: uppercase, trimmed) and mailing address. Each unique owner is traced once, regardless of how many parcels they own.

### 3. Estimate Cost
Before running the trace, calculate and display the estimated cost:
- Count of unique owners to trace
- Cost per lookup: ~$0.007
- Total estimated cost: count * $0.007
- **Pause and confirm with the user before proceeding** (this step costs real money)

### 4. Call Apify Skip Trace Actor
Use the Apify actor `one-api~skip-trace` for batch lookups:
```python
# Via Apify API
POST https://api.apify.com/v2/acts/one-api~skip-trace/runs
{
    "input": {
        "queries": [
            {"name": "JOHN SMITH", "address": "123 Main St, City, ST 12345"},
            ...
        ]
    }
}
```
- API key is stored in `.env` as `APIFY_API_TOKEN`
- Submit in batches if >100 owners (API may have batch limits)
- Poll for completion or use webhook

### 5. Parse Results
For each result returned:
- Extract phone numbers (may have multiple — mobile, landline, etc.)
- Extract email addresses
- Extract age/date of birth if available
- Match back to the owner by name + address

### 6. Create Owner Records
For each unique owner:
```python
owner = Owner.objects.update_or_create(
    name=normalized_name,
    mailing_address=address,
    defaults={
        'phones': phones_json,
        'emails': emails_json,
        'age': age,
    }
)
# Link to all parcels this owner holds
for parcel in owner_parcels:
    parcel.owner_fk = owner
    parcel.save()
```

### 7. Save Raw Results
Write the full API response to `.tmp/{buyer}/{county}/skip_trace_results.json` for debugging and audit purposes.

### 8. Log Summary
Report:
- Total owners traced
- Owners with phone numbers found: N
- Owners with email found: N
- Owners with no contact info: N
- Total cost incurred

## Decision Points
- **Cost threshold**: If the estimated cost exceeds $50 (roughly 7,000+ lookups), confirm with the user — something may be off with the filtering (too many parcels rated).
- **No results for an owner**: Some owners are untraceable (trusts, LLCs, deceased). Mark them as `trace_status = "no_results"` and move on.
- **Multiple phone numbers**: Store all of them. The outreach step (outside this pipeline) will determine which to call first (mobile preferred over landline).
- **Owner already traced**: If an Owner record already exists (from a prior pipeline run or different BuyBox), skip the API call and reuse existing contact info. Only re-trace if the data is older than 90 days.

## Edge Cases
- Corporate owners (LLCs, trusts) — skip trace may not return useful results; consider using a registered agent lookup instead
- Deceased owners — skip trace may return outdated info; the heir or estate executor is the real contact
- Owner name is a couple ("SMITH JOHN & JANE") — trace the primary name, note the secondary
- Mailing address is a PO Box — skip trace can still work but results may be less reliable

## Self-Annealing
- If the Apify actor changes its input/output format, update the request and parsing logic in the script. Check the actor's documentation page for the latest schema.
- If skip trace results have low hit rates (<50% with phone numbers), try an alternative provider or supplement with a second service.
- If the API rate-limits or fails mid-batch, implement retry logic with exponential backoff. Save partial results so the re-run only traces remaining owners.
- Track cost per run in a log file. If costs trend upward, review whether the rating step is letting too many parcels through.
