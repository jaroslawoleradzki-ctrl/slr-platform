# Search pipeline and Boolean-query semantics

The versioned `SearchQuery` AST is the source of truth for every Search execution. A rendered
provider string is a physical retrieval query, never a replacement for the canonical query.
Every execution records `canonical_query_id`, `canonical_version`, and a SHA-256
`canonical_hash` calculated from the version and stable JSON representation of the AST.

## Processing order

```text
Canonical SearchQuery AST
  -> provider translation and physical-query metadata
  -> candidate retrieval
  -> normalization
  -> local canonical validation
  -> metadata constraints
  -> DOI deduplication with provenance union
  -> snapshot/audit persistence
  -> screening import selected by the user
```

Canonical validation evaluates the complete recursive AST. `OR` is evaluated within concept
blocks and `AND` between required blocks; `NOT` and explicitly scoped terms are also supported.
Matching uses Unicode normalization and case folding. A phrase is an ordered, contiguous token
sequence, not an unordered bag of words. Canonical `ANY` terms use title and abstract. Explicit
`keywords`, `author`, and `venue` scopes use only the corresponding canonical publication field.

Validation has three outcomes:

- `match`: the available fields prove the expression;
- `non_match`: available fields disprove it;
- `indeterminate`: a required scoped field is missing, so rejection would risk a false negative.

Indeterminate records are retained with a warning. Missing data is never treated as a positive
match.

## Provider translations

### OpenAlex

The complete parenthesized Boolean expression is sent in the `/works` `search` parameter.
Quotes and `AND`/`OR`/`NOT` are retained. The translation is marked lossy because OpenAlex
search can also match full text whereas local canonical `ANY` validation is limited to title and
abstract. Results therefore remain a candidate set and receive canonical validation.

### Crossref

Crossref REST free-text query does not execute the canonical Boolean tree. The adapter marks the
translation lossy and creates a bounded positive-anchor plan. For an `AND`, it retrieves the
smallest required positive child plan; for an `OR`, it unions child queries. This produces a
candidate superset without generating the Cartesian product of all blocks. Source IDs are
deduplicated across physical requests, and every candidate receives canonical validation.

Crossref metadata frequently omits publication abstracts. When abstracts are absent and cannot be
enriched via external DOI lookup, local canonical validation cannot definitively evaluate
abstract-dependent Boolean expressions. In such cases, candidates are marked as `indeterminate` and
retained to prevent false negatives. When indeterminate records exceed 50% of retrieved records, a
prominent warning is reported in the execution status and audit logs.

### Semantic Scholar

The adapter uses `/graph/v1/paper/search/bulk` and maps `AND` to `+`, `OR` to `|`, phrases to
quotes, and preserves parentheses (with unary exclusion for `NOT`). Unsupported canonical field
scopes make the translation explicitly lossy. Supported bulk filters are placed in their native
parameters; an unsupported language filter is disclosed and enforced later where metadata exists.

## Audit and counts

`search_run_audits` stores the canonical identity, provider, physical endpoint and query,
losslessness flag, warnings, timestamps, and these distinct counts:

- `retrieved_count`: unique provider records received before canonical validation;
- `canonical_accepted_count`: matches plus retained indeterminate records;
- `canonical_rejected_count`: proven canonical non-matches;
- `canonical_indeterminate_count`: retained records that could not be decided because a required
  field was absent;
- `deduplicated_count`: DOI duplicates removed after provider results are combined.

Snapshot publications retain all provenance entries after DOI deduplication. Thus one canonical
publication may identify both an OpenAlex retrieval and a Crossref retrieval, including their run
IDs and physical rendered queries.
