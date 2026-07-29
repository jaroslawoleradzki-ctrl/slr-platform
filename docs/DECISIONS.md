# Architectural Decisions

This document records important project decisions that do not require a full ADR.

---

## 2026-07-29

### Deterministic publication merge policy

Phase 5.2 introduces an infrastructure-independent `PublicationMergePolicy`
for two publications that have already been identified as the same work. The
policy does not detect duplicates and is not integrated into Search Engine.
The existing `ResultMerger` retains its conservative first-normalized-DOI,
first-record behavior.

Merge output is independent of argument order. The lowest technical record UUID
and earliest creation time are retained. Different publication schema versions
raise an explicit conflict; equal versions are preserved. Longer non-empty
title, abstract, and publisher values win, with a stable lexical tie-break.
The selected title is normalized again. Two different explicit language values
raise a conflict; otherwise the available language is retained. The more
complete ordered author list and venue win as whole values; author identity
resolution and list interleaving are excluded. A full publication date wins
over a year-only value. When both records contain different full dates, the
later full date and its matching year win deterministically. Keywords and URLs
are deduplicated and stably ordered.

Identifier values are deduplicated and stably ordered. DOI values use canonical
DOI normalization. DOI, PMID, and OpenAlex identifiers are treated as unique
work identifiers, so distinct values of one of those types raise an explicit
merge conflict. Multiple ISSN, ISBN, ORCID, and `OTHER` values may coexist.
Conflicting explicit open-access values also raise rather than being silently
prioritized.

All distinct existing `ProvenanceEntry` records from both inputs are preserved
in stable order. Because the current provenance model is record-oriented rather
than field-oriented, it cannot retain an explicit association between every
discarded alternative scalar value and its source. Phase 5.2 does not introduce
a parallel provenance system.

---

## 2026-07-28

### Post-mapping publication normalization pipeline

Phase 4.5 establishes `app/normalization/publication.py` as the single
provider-independent pipeline for one complete canonical `Publication`.
`PublicationNormalizer` composes the existing title, author, DOI, and ORCID
normalizers and introduces no new value-normalization algorithm.

The pipeline preserves the original title and populates `title_normalized`.
It normalizes author name whitespace, publication DOI values, and author ORCID
values. ISSN, ISBN, PMID, OpenAlex, `OTHER`, and all other identifier types
remain unchanged. It neither removes nor deduplicates any identifiers,
authors, affiliations, keywords, or other collection elements.

Normalization returns a new deeply copied `Publication` while preserving
record ID, schema version, creation time, provenance, dates, collection order,
and every field outside the explicit normalization scope. It performs no
matching, filtering, merging, identity resolution, or parser heuristics.
Repeated DOI or ORCID values therefore remain repeated after normalization;
deduplication is a Phase 5 responsibility.

The pipeline runs exactly once as an explicit post-mapping orchestration step.
Search Engine applies it to successful provider publications before building
provider results, result provenance, and merged results. BibTeX and RIS import
providers apply it after their mappers return. Mapper behavior and
`ResultMerger` behavior remain unchanged.

---

### Canonical author and ORCID normalization boundaries

Phase 4.4 adds `AuthorNormalizer`, which accepts one already constructed
canonical `Author` and returns a new deeply copied `Author`. It collapses and
trims whitespace only in `display_name`, `given_name`, and `family_name`.
Capitalization, diacritics, punctuation, initials, suffixes, prefixes, name
order, and absent optional name parts remain unchanged.

The normalizer neither parses nor reconstructs `display_name`. Provider mappers
remain responsible for source-specific schemas, while BibTeX and RIS mappers
remain responsible for their format-specific author parsing. Systematic
normalization of author lists within `Publication` is deferred to Phase 4.5.
The legacy `app.modules.normalize.service` has no author re-export because its
`PublicationRecord` stores `authors` as `list[str]`, not canonical `Author`
objects.

Author normalization performs no matching, identity resolution,
disambiguation, deduplication, fingerprinting, or merging. Identifier and
affiliation values are not normalized by `AuthorNormalizer`; they are only
deeply copied to avoid sharing mutable lists with the input.

`app/normalization/orcid.py` is the single source of ORCID normalization
behavior. It preserves the former provider-boundary semantics: trimming,
case-insensitive removal of supported URL prefixes, removal of a trailing
slash, and uppercasing only a final `x`. The provider mapping utility keeps a
compatibility re-export, while active providers import the neutral API
directly. This is value normalization only, without checksum validation,
existence checks, author matching, or identity resolution.

---

### Provider-independent title normalization

Phase 4.3 establishes `app/normalization/title.py` as the single source of
title-normalization behavior. `TitleNormalizer` implements the structural
normalization contract, while `normalize_title` provides the public convenience
function. The implementation is provider-independent, deterministic,
idempotent, and non-mutating.

The canonical algorithm preserves the legacy sequence: Unicode NFKC
normalization, case folding, replacement of characters outside `\w` and
whitespace with spaces, whitespace collapsing, and trimming. Non-string,
blank, and punctuation-only inputs return `None`.

This normalization produces a stable textual representation only. It performs
no fuzzy matching, similarity or confidence scoring, transliteration,
translation, token sorting, stemming, lemmatization, or stop-word removal.
Author and publication-wide normalization remain later-phase responsibilities.

`app.modules.normalize.service` re-exports the canonical function solely for
compatibility with its legacy `normalize_record` pipeline; it contains no
second title-normalization algorithm.

---

### Provider-independent DOI normalization

Phase 4.2 establishes `app.normalization.doi` as the single source of DOI
normalization behavior. `DoiNormalizer` implements the structural normalization
contract, while `normalize_doi` exposes the same behavior as a convenience
function. The implementation is deterministic, idempotent, non-mutating, and
provider-independent.

The provider mapping utility re-exports the canonical function to preserve
existing imports without retaining a second algorithm. `ResultMerger` imports
the canonical normalization API directly, removing its dependency on the
provider layer without changing merge behavior.

Normalization trims strings, rejects blanks and non-strings, removes only the
supported case-insensitive prefix at the beginning, and lowercases the result.
It deliberately performs neither strict DOI syntax validation nor existence
checks. Title and author normalization, publication-wide normalization, and
deduplication decisions remain responsibilities of later phases.

---

### Normalization layer responsibility boundaries

Phase 4.1 introduces only a structural normalization contract. Provider-boundary
cleaning continues to operate on raw external values inside provider adapters
and mapping utilities. It safely reads provider-specific shapes, trims strings,
handles blanks and invalid external types, and performs the light conversion
needed to build valid canonical models.

Global normalization operates on canonical values or canonical domain objects.
Its implementations must be provider-independent, deterministic, idempotent for
their supported inputs, and non-mutating. A normalizer handles one value or
object and produces a stable representation while preserving semantic content.

Deduplication remains a separate Phase 5 responsibility. It compares multiple
records, decides duplicate/not-duplicate relationships, selects or merges
records, and may later calculate similarity or confidence. The normalization
API therefore exposes no collection processing, duplicate candidates, match
scores, winning-record selection, or merge behavior.

The public Phase 4.1 API consists only of the generic structural
`Normalizer[InputT, OutputT]` protocol. No concrete DOI, title, author,
identifier, or publication normalizer and no normalization result model is
introduced.

Existing `normalize_doi`, `normalize_orcid`, `normalize_issn`, `normalize_url`,
and related provider mapping helpers are not migrated in Phase 4.1.
Provider-independent DOI normalization and migration begin in Phase 4.2.

---

### Search Engine public contract suite

Phase 3.6 closes the planned Search Engine layer with contract tests that enter
only through `SearchEngine.execute()`. The suite uses the real Search Engine,
ResultMerger, domain objects, raw archive entries, and provenance models.

Only external boundaries are replaced: structural fake providers return
controlled `ProviderSearchOutput` values, an in-memory fake archive records save
attempts and successful writes, and deterministic factories supply timestamps,
SearchRun IDs, and archive IDs. No HTTP client, server, network fixture, or
concrete provider is used.

The contract scenarios cover single- and multi-provider execution, partial
provider failures, raw-response archiving, archive-failure propagation,
DOI-only merge, per-publication provenance, aggregate execution provenance,
empty results, no providers, deterministic timing, and consistent query/run
associations.

These tests add no product behavior and require no production-code change.
Completion of Phase 3 means the roadmap's orchestration layer and verification
are complete, not that runtime persistence or deployment infrastructure exists.

---

### Immutable Search Engine execution provenance

Phase 3.5 records final provider runs and an execution-level summary without
mutating canonical `Publication` objects. Each provider receives a validated
`RUNNING` SearchRun immediately before its request. After the required archive
write succeeds, a new fully validated SearchRun is created as `COMPLETED` or
`FAILED`; frozen Pydantic models are not bypassed.

Provider timing covers request processing and the mandatory raw-response
archive write. Start and finish timestamps come from the injected Search Engine
clock, and duration is derived from them in seconds. Successful runs record the
number of canonical publications. Failed runs record zero results, one stable
`ExceptionType: message` diagnostic, and retain the original exception in
`ProviderSearchResult`.

`PublicationSearchProvenance` associates each original publication from a
successful provider with that provider and its completed SearchRun. Provenance
is produced in provider/publication order. DOI duplicates retain separate
per-provider provenance entries; merge does not combine provenance.

`SearchExecutionProvenance` indexes ordered provider run IDs and summarizes
execution timestamps, duration, total canonical results before merge, and the
merged result count. It references rather than duplicates full SearchRun data.

Archive failures still propagate before a final provider result, merge, or
execution provenance can be produced. No persistence, repository, tracing,
telemetry backend, field-level provenance, or Phase 3.6 contract layer is added.

---

### Conservative DOI-only provider result merge

Phase 3.4 adds a separate stateless `ResultMerger`, invoked once after all
providers have executed sequentially and their required raw responses have been
archived. `SearchExecution` retains every per-provider result and additionally
exposes one merged publication list.

Only publications from successful providers enter the merge. Input order is
provider order followed by each provider's publication order, and the output
keeps the first occurrence of each normalized DOI. The first matching
`Publication` object is retained unchanged; later objects with that DOI are
omitted without merging fields or provenance.

DOI keys use the canonical provider-independent `normalize_doi` behavior from
`app/normalization/doi.py`, including supported URL and `doi:` prefixes and case
normalization. If a publication has multiple DOI identifiers, the first DOI in
identifier order is the deterministic key. Other DOI identifiers and all
non-DOI identifier types are ignored for matching.

Publications without a DOI are never combined, even when other metadata is
identical. No title, author, year, venue, similarity, ranking, best-record
selection, or metadata enrichment is performed.

Raw-response archiving and provider failure isolation are unchanged. An archive
failure still propagates before a final `SearchExecution` or merge result can be
created.

---

### Raw provider response archive boundary

Phase 3.3 captures raw responses directly at the provider boundary rather than
reconstructing them from canonical `Publication` objects. A
`ProviderSearchOutput` carries both the mapped publications and the ordered raw
response pages produced by the same request.

One `RawResponseArchiveEntry` corresponds to one `SearchRun`. It records the
provider, rendered query, capture timestamp, success or failure status, raw
pages, and minimal failure diagnostics. Ordered pages are retained without
interpretation, merging, or deduplication.

`RawResponseArchive` is an explicit asynchronous dependency of `SearchEngine`.
Archive IDs and the capture clock are injected for deterministic execution and
tests. Provider failures are archived and remain isolated so later providers
can run. An archive storage failure is propagated unchanged and stops execution,
because silently losing required raw material would make a successful result
misleading.

OpenAlex and Crossref retain their public publication-only `search()` API and
add `search_with_raw()` for orchestration. Both paths share the same request and
mapping operation, so archiving does not issue a second HTTP request. Semantic
Scholar currently has a raw client and mapper but no public provider `search()`
method, so Phase 3.3 does not invent a new orchestration API for it.

Current orchestration searches fetch one page. Existing multi-page iterators
yield mapped records and do not expose raw page boundaries. If a provider fails
before returning its output, partial pages cannot be archived safely without a
larger callback mechanism; the failed entry records no responses and retains
error diagnostics.

No database, file, or object-storage implementation is introduced in this
phase. Persistence infrastructure, merge behavior, and interpretation of raw
payloads remain outside Phase 3.3.

---

### Sequential multi-provider orchestration

Phase 3.2 extends the Search Engine from one provider to an explicitly ordered
sequence of providers. Providers run sequentially in constructor order, keeping
execution deterministic and avoiding concurrency policy before the roadmap
introduces a need for it.

Each provider receives its own `SearchRun`, and its publication list remains in
a separate `ProviderSearchResult`. A single provider failure is isolated in that
provider's result as the original exception, while later providers continue to
run. This keeps partial successes and errors visible in the same deterministic,
ordered result.

The Search Engine does not merge or deduplicate results because cross-provider
record combination belongs to later roadmap phases.

---

### Minimal single-provider Search Engine orchestration

Phase 3.1 introduces a provider-independent Search Engine that accepts one
canonical `SearchQuery` and invokes exactly one provider supplied explicitly to
the engine.

The Search Engine creates one `SearchRun` before invoking the provider. The run
uses the canonical query ID and version, the provider's declared name, the
generic Boolean query rendering, and an injectable run ID factory. The provider
receives that same query and run.

Search providers satisfy a minimal structural `SearchProvider` protocol. They
remain responsible for HTTP, retries, provider-specific response handling, and
canonical mapping. The Search Engine neither imports concrete providers nor
duplicates their mapping logic.

The execution result contains the created run and the exact publication list
returned by the provider. Provider ordering and object identity are preserved,
including for an empty list. Provider exceptions propagate unchanged.

This increment deliberately excludes multiple-provider orchestration, fallback,
merge, raw response archive, deduplication, aggregated search provenance,
persistence, result counts, duration tracking, and failure status recording.

Search Engine tests use a structural fake provider and perform no real or
transport-mocked HTTP calls.

---

## 2026-07-24

### RIS Parser implementation

Added a simple, dependency-free sequential line parser for RIS format files via `app/providers/import_file/ris/parser.py`.

Key decisions:
- **Exposed API**: Exposes exactly one public function `parse_ris(content: str) -> list[dict[str, list[str]]]`.
- **Parsing Strategy**: Use a sequential line reader with a compiled regex for tag detection rather than a regex-heavy implementation.
- **Tag-value storage**: Preserve tag casing exactly as it appears in the input. Map every tag to a list of strings (`list[str]`) to natively handle repeating tags (e.g. `AU` for authors, `KW` for keywords) without data loss.
- **Multiline continuations**: A non-blank, non-tag line inside an open record is treated as a continuation of the most recently parsed field. The trimmed text is appended to the last value of that field, separated by a single space. Continuation lines outside a record or before any field raise `ValueError`.
- **Structural Validation**: Raise `ValueError` on malformed tag-like lines (lines that resemble a tag but do not match the exact `XX  - value` format), nested `TY` tags, `ER` before `TY`, any field tag before `TY`, and EOF inside an unclosed record.
- **Blank lines and whitespace**: Blank lines are ignored everywhere. Whitespace around tag values is trimmed. RIS tags are always required at the beginning of the line — no tag inference from indented or continuation lines.

Verified quality state:
- 206 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### RIS → Publication mapping

Added `map_ris_record(record, *, source) -> Publication` in `app/providers/import_file/ris/mapper.py`.

Key decisions:
- **Single pure function**: No class, no state, no I/O. Accepts the dict produced by `parse_ris()` and a caller-supplied `source` string.
- **Source string**: Identifies the bibliography origin (e.g. `"google_scholar"`, `"zotero"`), not the file format. Blank source raises `ValueError`.
- **Title precedence**: `TI` → `T1` → `CT`. Raises `ValueError` if all three are absent or blank.
- **Abstract precedence**: `AB` → `N2`. Absent → `None`.
- **Authors**: `AU` used exclusively when present; `A1` is the fallback. Names containing `, ` are split into `family_name` and `given_name`. Plain-format names set `display_name` only. Blank entries silently skipped.
- **Publication year**: `PY` preferred, `Y1` as fallback. Parsed as `int`; malformed or out-of-range values silently ignored (`publication_year=None`).
- **Document type**: TY tag value mapped via `_TY_TO_DOC_TYPE` dict. Unknown or absent TY → `DocumentType.OTHER` (consistent treatment — no silent `None`).
- **DOI normalization**: Delegates to the canonical provider-independent implementation in `app/normalization/doi.py`. The older `app.modules.normalize.service` module retains only a compatibility import for its legacy pipeline.
- **Provenance `source_record_id`**: Normalized DOI when available; title as deterministic fallback. No `ValueError` is raised for records without a DOI — consistent with the import use case where many records lack one.
- **Postponed to later increments**: venue, ISSN/ISBN, PMID/PMC, keywords, URLs, language, publisher, `publication_date`, date-consistency logic.

Verified quality state:
- 259 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Google Scholar RIS import

Added `import_ris(content: str) -> list[Publication]` in `app/providers/import_file/ris/google_scholar.py`.

Key decisions:
- **Thin integration layer**: Composes `parse_ris()` and `map_ris_record()` with no additional logic. Three lines of implementation.
- **Source fixed to `"google_scholar"`**: The module and its provider are Google Scholar-specific, so this source is assigned to `GoogleScholarImportProvider`.
- **No error suppression**: Parse and mapping errors propagate naturally. The caller decides whether to abort or skip bad records. Strict/lenient mode is explicitly deferred.
- **Empty input → empty list**: Consistent with `parse_ris("")` returning `[]`.
- **Record ordering preserved**: Publications are returned in the same order as records appear in the file.

Verified quality state:
- 279 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### ImportProvider abstraction

Added `ImportProvider` in `app/providers/import_file/base.py` as the common contract for publication importers.

Key decisions:
- **Structural contract**: `ImportProvider` uses `typing.Protocol`, not an ABC base class. Implementations conform by structure without explicit inheritance.
- **Minimal API**: The contract contains only `import_publications(content: str) -> list[Publication]`.
- **Serialized input boundary**: The abstraction accepts already serialized content as `str`. File reading and user-interface concerns remain outside the provider.
- **First implementation**: `GoogleScholarImportProvider` is the first implementation of the contract.
- **Compatibility wrapper**: `import_ris(content)` remains public and delegates to the Google Scholar provider.
- **Preserved responsibilities**: The RIS parser and mapper retain their single responsibilities and were not changed.
- **Deferred infrastructure and formats**: No provider registry, factory, format autodetection, or BibTeX support was added.
- **Contract verification**: One contract test confirms the structural compatibility of `GoogleScholarImportProvider` with `ImportProvider`.

Verified quality state:
- 280 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### BibTeX parser

Added a dependency-free BibTeX parser in `app/providers/import_file/bibtex/parser.py`.

Key decisions:
- **Custom deterministic scanner**: The parser uses no external parsing library and processes serialized BibTeX content character by character.
- **Raw record model**: `BibTeXRecord` separates entry metadata (`entry_type` and `citation_key`) from its `fields` dictionary.
- **Identifier normalization**: Entry types and field names are normalized to lowercase, while citation keys remain unchanged.
- **Value boundaries**: Only external braces or quotes and surrounding whitespace are removed. Nested braces remain part of the value.
- **No LaTeX interpretation**: Text inside field values is preserved without decoding or normalization.
- **Comment handling**: `%` starts a comment only outside field values, and `@comment` entries are ignored.
- **Unsupported constructs**: `@string` and `@preamble` remain outside the supported scope and raise `ValueError`.
- **Architectural isolation**: The parser has no knowledge of `Publication`, `ImportProvider`, or the RIS parser.
- **Dependencies**: No new dependencies were added.

Verified quality state:
- 303 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### BibTeX to Publication mapping

Added `map_bibtex_record(record, *, source) -> Publication` in `app/providers/import_file/bibtex/mapper.py`.

Key decisions:
- **Pure mapping boundary**: The mapper accepts one already parsed `BibTeXRecord`; parsing and mapping remain separate, and the mapper performs no file I/O.
- **Required source**: `source` is a mandatory keyword-only argument and must be non-blank.
- **Existing domain and normalization**: The mapper uses the canonical `Publication`, `Author`, `Venue`, `Identifier`, and `ProvenanceEntry` models together with the existing `normalize_doi` helper.
- **Authors**: The word `and` separates authors only outside braces. `Family, Given` and `Given Family` forms populate canonical name parts. A brace-protected corporate author uses `display_name` only. Advanced BibTeX name rules remain outside scope.
- **Document types**: `article` maps to `JOURNAL_ARTICLE`; `book` to `BOOK`; `inbook` and `incollection` to `BOOK_CHAPTER`; `inproceedings`, `conference`, and `proceedings` to `CONFERENCE_PAPER`; `phdthesis` and `mastersthesis` to `DISSERTATION`; `techreport` to `REPORT`; and `misc` to `OTHER`. Unknown types fall back to `OTHER`.
- **Venue precedence**: The first non-blank value from `journal`, `booktitle`, and `publisher` becomes the minimal venue representation.
- **DOI and source record identity**: DOI values use `normalize_doi`. Provenance `source_record_id` prefers normalized DOI, then citation key, then title.
- **Provenance**: Each publication receives source provenance with a timezone-aware retrieval timestamp and `transformation="bibtex_to_publication"`.
- **Text preservation**: Titles and other values retain their parsed LaTeX text without decoding.
- **Deferred scope**: Parser changes, provider integration, compatibility wrappers, advanced names, LaTeX decoding, macros, concatenation, registry, autodetection, and Harmonization remain outside this increment.

Verified quality state:
- 343 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### BibTeX ImportProvider

Added `BibTeXImportProvider` in `app/providers/import_file/bibtex/provider.py`.

Key decisions:
- **Thin orchestration layer**: The provider composes the existing parser and mapper without duplicating either responsibility.
- **Separated layers**: `parse_bibtex`, `map_bibtex_record`, and `BibTeXImportProvider` remain independent parsing, mapping, and orchestration layers.
- **Structural contract**: The provider satisfies `ImportProvider` structurally and does not inherit from a base class.
- **Source configuration**: A keyword-only constructor argument configures `source`, defaulting to `"bibtex"`, and the value is passed unchanged to every mapper call.
- **Ordering and empty input**: Publications preserve parser record order, while empty content produces an empty list.
- **Error propagation**: Parser and mapper errors propagate unchanged. Records are not skipped and partial success is not supported.
- **Stateless imports**: The provider performs no I/O and retains no state between import calls beyond its immutable-by-convention source configuration.
- **Deferred infrastructure**: No compatibility wrapper, provider registry, factory, or format autodetection was added. Shared contract tests across providers remain Phase 4.4.
- **Dependencies**: No new dependencies were added.

Verified quality state:
- 362 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### ImportProvider contract tests

Replaced the minimal single-provider contract check with a shared parameterized suite in `tests/unit/providers/import_file/test_import_provider.py`.

Key decisions:
- **Multi-provider parameterization**: The same contract suite covers `GoogleScholarImportProvider` and `BibTeXImportProvider`.
- **Public API boundary**: Contract tests call only `provider.import_publications(content)` and do not invoke parsers or mappers directly.
- **Common behavior**: The suite covers empty and whitespace-only input, single and multiple records, result types, ordering, stateless consecutive calls, error propagation without partial success, and stable repeated-import results.
- **Stable equivalence**: Repeated results compare title, abstract, authors, publication year, document type, identifiers, venue, and stable provenance fields. Dynamic `retrieved_at`, `created_at`, and generated `record_id` values are excluded.
- **Format-specific coverage**: RIS, Google Scholar, BibTeX parser, mapper, and provider behaviors remain in their existing focused test modules.
- **Structural typing**: Both providers are passed through an `ImportProvider`-typed boundary, with mypy confirming compatibility. No inheritance or protocol change was introduced.
- **No production changes**: Existing providers already satisfied the shared contract, so neither provider required modification.
- **Deferred infrastructure**: No common base class, registry, factory, or format autodetection was added.
- **Dependencies**: No new dependencies were added.

Verified quality state:
- 377 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Harmonization implementation sequence

Harmonization is divided into five reviewable increments before work proceeds to the Search Engine and review workflow.

Key decisions:
- **Specification first**: Canonical mapping quality and field expectations are defined before provider production code is changed.
- **Five increments**: The sequence is canonical mapping parity specification, OpenAlex mapping parity, cross-provider normalization consistency, shared mapper utilities, and cross-provider mapping contract tests.
- **Crossref as a reference**: Crossref is currently the richest mapping and provides a useful reference, but it is not automatically the sole canonical specification.
- **OpenAlex before extraction**: OpenAlex parity is implemented before shared utilities are extracted, so abstractions are based on demonstrated duplication.
- **Evidence-based helpers**: Shared helpers will be introduced only for mapping logic that is genuinely repeated across providers; no general mapper framework or provider base class is planned.
- **Separated responsibilities**: Provider-specific API clients remain separate from canonical domain mapping.
- **Provider-boundary normalization**: Harmonization normalization covers only consistency at the provider → canonical model boundary.
- **Later phases remain separate**: Global Normalization, Deduplication, and Screening retain their own later roadmap phases.
- **Contract-test closure**: Shared mapping contract tests across OpenAlex, Crossref, and Semantic Scholar close the Harmonization phase while provider-specific cases remain separately tested.
- **Documentation-only planning**: This increment adds no production code, tests, models, or dependencies.

---

### Canonical mapping parity specification

Added `docs/MAPPING_PARITY.md` and a lightweight machine-checked matrix for OpenAlex, Crossref, and Semantic Scholar.

Key decisions:
- **Specification before implementation**: Mapping parity is defined and tested before any search-provider mapper is changed.
- **Reference, not monopoly**: Crossref is the richest current implementation and an important reference, but it is not the sole canonical specification.
- **Required auditability**: Required fields are limited to a valid title and complete source/search-context provenance needed for an auditable canonical search result.
- **Provider-dependent data**: Missing provider data is not an error for optional fields and must result in `None` or an empty collection rather than fabricated values.
- **Generated metadata**: `record_id`, `schema_version`, and `created_at` remain canonical model responsibilities.
- **Deferred title normalization**: `title_normalized` remains part of the later global Normalization phase.
- **Explicit OpenAlex gaps**: The title-only OpenAlex mapping baseline and its candidate response fields are registered for Phase 5.2 without implementing them.
- **Sequenced consistency work**: Identifier and boundary normalization remains Phase 5.3; shared helpers remain Phase 5.4 and require demonstrated duplication.
- **Specification tests**: Tests verify field coverage, uniqueness, classifications, provider baselines, targets, required title/provenance, generated/deferred metadata, OpenAlex gaps, and agreement with the documented matrix.
- **No expected failures**: The suite contains no xfail or intentionally failing tests.
- **No production change**: No production code, models, existing provider tests, or dependencies were changed.

Verified quality state:
- 388 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### OpenAlex canonical mapping parity

Expanded OpenAlex mapping from title-only output to the canonical fields that
have stable, semantically unambiguous sources in an OpenAlex work response.

Key decisions:
- **Transport remains separate**: `OpenAlexClient` continues to own HTTP, retry, rate limiting, and pagination only.
- **Public pure mapper**: `OpenAlexProvider.map_work()` maps one work without I/O, search context, timestamps, or provenance.
- **Separate provenance orchestration**: `search()` and `iterate()` validate the OpenAlex source ID, call the pure mapper, and attach complete search provenance through an immutable model copy.
- **Dual-purpose OpenAlex ID**: The full work ID remains the provenance source record ID and is also retained as a canonical provider-native `OTHER` identifier with `source="openalex"`.
- **Author names remain faithful**: OpenAlex `display_name` is retained without inventing `given_name` or `family_name`.
- **Deterministic abstracts**: Abstract text is reconstructed by position from `abstract_inverted_index`; for a position collision, the lexically first token is retained so JSON key order cannot affect the result.
- **Malformed optional data is omitted**: Invalid optional structures produce `None` or empty collections and do not reject an otherwise auditable publication.
- **Date conflict policy**: A valid explicit publication year is retained and a conflicting publication date is discarded.
- **No inferred keywords**: OpenAlex topics and concepts are not assumed to be publication-assigned canonical keywords.
- **No inferred publisher**: `host_organization_name` is not assumed to identify the publication publisher.
- **Local helpers only**: OpenAlex-specific parsing and mapping helpers remain in its provider module; shared helpers are deferred to Phase 5.4.
- **Normalization remains sequenced**: Cross-provider identifier and boundary consistency remains Phase 5.3.
- **Stable domain boundary**: No canonical domain model, other provider, or HTTP client was changed.
- **No dependencies**: No external dependency was added.

Verified quality state:
- 435 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Cross-provider boundary normalization

OpenAlex, Crossref, and Semantic Scholar now apply the same deterministic
normalization contract where their APIs expose semantically equivalent data.

Key decisions:
- **Whitespace and blanks**: Strings are trimmed, blank optional values are omitted, and non-string values are never stringified.
- **DOI**: HTTP/HTTPS `doi.org` and `dx.doi.org` prefixes plus `doi:` are removed, then DOI values are lowercased. No checksum or syntax regex was added.
- **Crossref provenance**: Its DOI-based `source_record_id` uses the same canonical DOI value as the publication identifier.
- **ORCID**: HTTP/HTTPS `orcid.org` prefixes and trailing slashes are removed and a final `X` is uppercased; no checksum validation is performed.
- **ISSN**: Values are trimmed, a final `X` is uppercased, and exact normalized duplicates are removed in first-seen order without adding punctuation or validating checksums.
- **Provider-native identifiers**: Values are non-blank and case-preserving `OTHER` identifiers with canonical sources `openalex` and `semantic_scholar`; Crossref does not duplicate DOI as `OTHER`.
- **URLs**: Only HTTP(S) strings are retained. Scheme matching is case-insensitive, only scheme casing is canonicalized, and the remaining URL is preserved.
- **Language**: Clean non-blank strings are passed to `Publication`; its existing lowercase and minimum-length validation remain authoritative.
- **Types**: Known document and venue types map case-insensitively, unknown non-blank strings map to `OTHER`, and missing, blank, or malformed types map to `None`.
- **Author names**: Provider order and casing are preserved, blank/malformed authors are skipped, full names are not split, and Crossref retains separately supplied given/family names.
- **Venue and publisher**: Values are trimmed and never inferred from fields with different semantics.
- **Year and date**: Years exclude booleans and remain within 1000–9999. Valid full dates may infer a missing year; a conflict preserves the explicit year and omits the date. Partial Crossref dates supply only their available year.
- **Malformed optional data**: Invalid optional values become `None` or empty collections; canonical-owned validation such as malformed non-blank language remains visible.
- **Boundary only**: This does not set `title_normalized`, resolve entities, merge records, or deduplicate publications and is not the later global Normalization phase.

Verified quality state:
- 478 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Temporary provider-local normalization helpers

Similar DOI, identifier, ISSN, URL, and string-cleaning logic intentionally
remains local to each provider during Phase 5.3.

Key decisions:
- **Evidence before extraction**: Phase 5.4 will compare the now-tested duplication and extract only genuinely common behavior.
- **No premature framework**: No mapper framework, base provider class, mixin, registry, or shared helper module was introduced.
- **Transport stays separate**: Provider API clients remain independent from canonical mapping.

---

### Shared provider mapping utilities

Phase 5.4 consolidates only normalization behavior proven identical across
OpenAlex, Crossref, and Semantic Scholar during Phase 5.3.

Key decisions:
- **Evidence-based extraction**: Duplication was retained through Phase 5.3 so extraction could follow tested behavior rather than anticipated reuse.
- **One small module**: `app/providers/search/mapping_utils.py` contains pure functions for string cleaning and DOI, ORCID, ISSN, and HTTP(S) URL normalization.
- **Functions over framework**: Stateless functions preserve transparent control flow without a base mapper, protocol, strategy hierarchy, registry, or dependency injection.
- **Provider structures remain local**: Date formats, author and affiliation structures, abstract formats, venue structures, document-type maps, collection ordering, and provenance remain provider-specific.
- **Transport independence**: The module imports no provider client and performs no I/O or network validation.
- **Stable behavior**: Provider APIs, canonical values, ordering, error messages, and provenance remain unchanged from Phase 5.3.
- **Boundary only**: The helpers serve provider → canonical mapping and do not implement global title/entity normalization, record merging, or deduplication.
- **No dependencies**: No external dependency was added.

Verified quality state:
- 524 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Cross-provider runtime mapping contracts

Phase 5.5 closes Harmonization with runtime regression contracts for OpenAlex,
Crossref, and Semantic Scholar canonical mapping.

Key decisions:
- **Mapping-only execution**: Contract tests call mapper methods directly and use no HTTP clients, transports, search operations, iteration, or network fixtures.
- **Test-only adapter**: A small immutable case model supplies each provider's mapper, rich fixture, minimal fixture, malformed fixture, and expected canonical snapshot without introducing production abstractions.
- **Shared invariants, separate fixtures**: Providers share canonical expectations while retaining response structures and snapshots appropriate to their APIs.
- **Filtered snapshots**: Assertions cover mapper-owned canonical fields and omit generated `record_id`, `created_at`, and other model-owned metadata.
- **Explicit provider differences**: Structured Crossref names and publisher, OpenAlex author metadata, Semantic Scholar PMID/provider ID, and differing venue support remain valid provider-data-dependent behavior.
- **Stable provenance**: Fixed query/run IDs, retrieval timestamp, rendered query, provider source, and source record ID make provenance deterministic without I/O.
- **Three test layers**: Helper unit tests protect pure normalization functions, cross-provider normalization tests protect boundary use, and runtime mapping contracts protect complete canonical output.
- **No production change**: Existing Phase 5.4 code satisfied the runtime contract; no mapper, domain model, client, or dependency was changed.

Verified quality state:
- 540 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar provenance

Implemented provenance mapping support in `SemanticScholarProvider.map_paper` to record search query details in the `provenance` field, mirroring OpenAlex's provenance construction.

Key decisions:
- **Provenance Context**: The `map_paper` method accepts `search_run`, `search_query`, and `retrieved_at` as required keyword-only arguments.
- **Mandatory paperId**: `paperId` is required to populate the `source_record_id` field in the `ProvenanceEntry`. If missing or blank (including whitespace-only strings), a `ValueError` is raised.
- **Provenance Construction**: Creates a single `ProvenanceEntry` with `source="semantic_scholar"`, `source_record_id=paper_id`, and search query metadata.

Verified quality state:
- 190 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar provider mapping to Publication

Added a mapping layer from Semantic Scholar Graph API paper records to the canonical `Publication` domain model via `SemanticScholarProvider.map_paper`.

Key decisions:
- **Title Mapping**: Requires a valid non-blank title string, raising `ValueError` if missing or blank.
- **Author Mapping**: Extracts author display name (`name` field) and skips records where a non-blank name cannot be formed, preserving the API-returned order.
- **Date Conflict Resolution**: If `publicationDate` and `year` disagree, `publication_year` is preserved and `publication_date` is omitted to avoid creating an internally inconsistent `Publication`.
- **Venue and ISSN**: Mapped from `publicationVenue` dict (including name, type, and ISSN list) with fallback to the top-level string `venue` if the name is not set.
- **Publication Type**: Uses a lookup table to translate `publicationTypes` list entries to canonical `DocumentType` values, falling back to `DocumentType.OTHER` for unrecognized types, and `None` if missing.
- **Identifiers**: DOI and PMID (from `externalIds.get("PubMed")`) are mapped to canonical identifiers, and `paperId` is stored as `IdentifierType.OTHER` with `source="semanticscholar"`.
- **Roadmap Boundaries**: Provenance is explicitly left empty (`[]`) for this increment.

Verified quality state:
- 187 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar offset pagination

`SemanticScholarClient` now supports multi-page result retrieval via `iterate_papers(...)` using offset pagination.

Key decisions:
- **API Suffix**: Directly query `{base_url}/paper/search` to cleanly capture response envelope pagination metadata fields (such as `next`).
- **Pagination Source of Truth**: The iterator relies solely on the `next` value returned in the response payload to determine the next page's offset.
- **Immediate Termination**: If a response's `"data"` field is empty or missing, iteration terminates immediately without processing `next` or firing any further HTTP requests.
- **Infinite Loop Protection**: If the `next` offset matches the current offset or was already visited in the same pagination sequence, iteration is halted with a `RuntimeError`.
- **API Error Handling**: Unparseable or non-integer `next` values trigger a `RuntimeError` rather than a `ValueError` (which remains reserved for input parameter validation).
- **Result Limit**: Supports an optional `max_results` constraint, terminating iteration cleanly after yielding the specified limit.

Verified quality state:
- 178 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Semantic Scholar basic client and single-page search

Added a low-level asynchronous client `SemanticScholarClient` in `app/providers/semantic_scholar.py` to search papers using the Semantic Scholar Graph API.

Key decisions:
- **Client Configuration**: `SemanticScholarClient` accepts `http_client`, `base_url`, and an optional `api_key`. If an API key is provided, it is sent via the `x-api-key` request header.
- **Search Suffix**: The API request is sent to the `/paper/search` endpoint relative to the configured `base_url`.
- **Search Suffix Slashes**: `base_url` trailing slashes are stripped to avoid malformed URL paths.
- **Validation**: Added validation ensuring query is non-empty, limit is positive, offset is non-negative, and fields is a non-empty list of non-blank strings. If `fields` is `None`, the fields parameter is omitted from the request.
- **Raw Records**: The `search_papers` method returns raw paper records from the response's `"data"` field as a list of dictionaries, returning `[]` if `"data"` is missing or null, without mapping them to `Publication`.
- **Error Propagation**: Standard HTTP errors are propagated via `raise_for_status()`.

Verified quality state:
- 169 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Crossref provider mapping to Publication

`CrossrefProvider` now maps raw Crossref Works API records to the canonical `Publication` domain model via `map_work`.

Key decisions:
- **Title Mapping**: Requires a list of titles; maps the first non-blank string, raising `ValueError` if missing or entirely blank. No fallback fields are used.
- **DOI Normalization**: Normalizes DOIs to lowercase and strips whitespaces. Kept in `identifiers` list, not exposed as individual fields.
- **Author Mapping**: Maps given/family names, ORCID (normalized from URLs by extracting the trailing path segment), and institutional affiliations (requires a non-empty name). Skips individual authors if a non-blank `display_name` cannot be formed, without failing the mapping of the entire publication.
- **Date Resolution**: Falls back through the hierarchy: `published-print` → `published-online` → `published` → `issued`. Parses standard date parts, mapping 3-part dates to both `publication_year` and `publication_date`, and 1/2-part dates to `publication_year` only, without introducing artificial days/months.
- **Venue and ISSN**: Mapped from the first non-empty `container-title` to `Venue`. ISSN values are mapped to `Venue.identifiers`. ISBN mapping is omitted for this increment.
- **Document Type Mapping**: Table-based mapping translates Crossref types to canonical `DocumentType` values, falling back to `DocumentType.OTHER` for unknown non-empty types, and `None` for missing ones.
- **Abstract Cleanup**: Cleans up HTML/XML/JATS tags and entity encodings from `abstract` string without external libraries, normalizing whitespaces.
- **Strict Boundary (No Provenance)**: The `provenance` field is intentionally left empty (`[]`) for this increment to respect roadmap boundaries.

Verified quality state:
- 154 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### Crossref cursor pagination

`CrossrefClient` now supports cursor-based pagination via the `iterate_works` asynchronous generator.

Key decisions:
- **Starting Cursor**: The initial request uses the standard starting cursor `*`.
- **Response Validation**: Response payloads are validated for `message.items` and `message.next-cursor` structure. A malformed `next-cursor` (present but not a string or blank) raises a `ValueError`.
- **Termination Conditions**: The iteration terminates normally when `items` is empty, when `next-cursor` is missing or null, or when the returned `next-cursor` equals the current cursor or a previously requested cursor (preventing infinite loops). Malformed cursor values (blank or non-string values) raise a `ValueError` instead of ending the iteration.
- **Optional Record Limit**: An optional `limit` parameter was introduced. If specified, the generator yields exactly up to the limit and stops without performing any unnecessary further HTTP page requests.
- **HTTP Reuse**: The pagination relies strictly on the existing `search_works` method, ensuring that rate limiting, retry semantics, and response structural validations are automatically inherited without duplicating HTTP logic.

Verified quality state:
- 134 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

## 2026-07-23

### Crossref retry and asynchronous rate limiting

`CrossrefClient` uses Tenacity for retries and a small custom asynchronous limiter for request pacing.

Retry covers only physical HTTP attempts and is limited to:

- `httpx.RequestError`
- HTTP 429
- HTTP 500
- HTTP 502
- HTTP 503
- HTTP 504

Other client errors, argument validation failures, and response JSON validation failures are not retried. The last original exception is propagated after exhaustion by using `reraise=True`.

Rate limiting is configured per `CrossrefClient` instance with `requests_per_second`:

- `None` disables limiting
- a finite positive number enables limiting
- zero, negative values, booleans, `NaN`, and positive or negative infinity are rejected

The limiter enforces a minimum interval between the starts of physical HTTP attempts. It is executed before every attempt, including retry attempts. An instance-local `asyncio.Lock` serializes request-start reservations, but the lock is released before HTTP I/O begins.

The monotonic clock and asynchronous sleep function are injectable, which keeps timing tests deterministic and avoids real waiting.

The Crossref implementation intentionally follows the proven OpenAlex behavior without introducing a shared base class, retry mixin, or shared rate-limiter abstraction at this stage.

Verified quality state:

- 121 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

### OpenAlex provenance mapping

`OpenAlexProvider` maps OpenAlex Works responses to canonical `Publication` models. `OpenAlexClient` remains a low-level HTTP client responsible only for communication, retry, rate limiting, response validation, and cursor pagination.

Each mapped publication receives a `ProvenanceEntry` containing:

- `source`
- `source_record_id`
- `query_id`
- `run_id`
- `rendered_query`
- `retrieved_at`

The search context is passed explicitly through `SearchRun` and `SearchQuery`. The retrieval clock is injectable so provenance timestamps remain deterministic in tests.

Archiving full raw JSON responses and storing publications or provenance are outside the scope of Phase 2.5. They remain responsibilities of later roadmap increments.

---

### OpenAlex asynchronous rate limiting

The OpenAlex provider uses a small custom asynchronous rate limiter rather than a third-party rate-limiting library.

Reasons:

- the required behavior is limited to enforcing a minimum interval between request starts
- adding a new external dependency would be disproportionate to the scope
- the limiter remains independent from Tenacity retry handling
- injected `clock` and `sleep` functions make timing behavior deterministic in tests

The limiter is configured with `requests_per_second`:

- a finite positive number enables limiting
- `None` disables limiting
- zero, negative values, `NaN`, and positive or negative infinity are rejected

The limiter state and `asyncio.Lock` belong to each `OpenAlexClient` instance. The lock serializes request-start reservations, but it is released before the HTTP response is awaited.

Rate limiting is applied immediately before every physical HTTP attempt. Therefore, it covers:

- normal search requests
- Tenacity retry attempts
- cursor-pagination requests

This preserves the existing retry and pagination semantics while ensuring that all outbound OpenAlex requests respect the configured rate.

Verified quality state:

- 73 tests passing
- Ruff checks passing
- mypy checks passing
- `git diff --check` passing

---

## 2026-07-22

### Retry implementation

The OpenAlex provider uses Tenacity for retry handling instead of a custom retry loop.

Reasons:

- retry logic will be reusable across multiple providers
- Tenacity supports asynchronous code
- exponential backoff and retry conditions are provided by a mature library
- this reduces custom infrastructure code and maintenance
- retry logic is not part of the scientific contribution of the project

The retry policy covers transient request failures and retryable HTTP statuses. Non-retryable client errors are propagated immediately.

---

### Roadmap governance

The roadmap is the authoritative sequence of implementation work.

New phases or intermediate stages should not be introduced implicitly.

Additional engineering activities, such as integration tests, should normally be treated as part of an existing roadmap item unless a deliberate decision is made to extend or change the roadmap.

---

### Phase 1 completion

Phase 1 — Domain Model is considered complete.

It includes:

- Publication
- Author
- Affiliation
- Venue
- Identifier
- SearchRun
- SearchQuery
- Provenance
- ScreeningDecision
- screening decision enum
- decision rationale
- reviewer or supporting agent attribution
- audit trail
- backward compatibility contract tests

---

### OpenAlex implementation status

Completed increments:

- 2.1 client
- 2.2 cursor pagination
- 2.3 retry with Tenacity
- 2.4 asynchronous rate limiting
- 2.5 provenance mapping

The next active increment is the Crossref provider implementation.

---

## 2026-07-21

### Infrastructure completed

The project infrastructure is considered stable.

Completed:

- GitHub repository
- HomeLab mirror
- SSH authentication
- FastAPI
- pytest
- development environment
- Docker-ready architecture

Future work should focus on scientific functionality rather than infrastructure.

---

### Architecture

The project adopts a lightweight Domain Driven Design.

Main layers:

- Domain
- Services
- Providers
- Workflow
- Storage

FastAPI acts only as the API layer.

---

### Scientific principles

The platform follows:

- provenance-first
- reproducibility
- deterministic processing
- human-in-the-loop

LLMs may assist the reviewer but must never make autonomous scientific decisions.

---

### Search strategy

The first implemented provider will be OpenAlex.

Additional providers will be added incrementally.

---

### Development strategy

Development proceeds in small reviewable increments.

Each increment should:

- pass tests
- include documentation
- preserve backward compatibility whenever practical
- be committed as an independent logical change

---

### Long-term vision

The SLR Platform is intended to become a reusable research tool rather than software dedicated only to the current PhD project.
