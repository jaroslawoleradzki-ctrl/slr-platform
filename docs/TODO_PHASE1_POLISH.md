# Phase 1 Polish Backlog

Backlog for the next sprint before beginning Phase 2.

### Critical

- [x] determine why OpenAlex reports thousands of results while the
  application returned 8 (`filter-after-limit`)
- [x] apply supported strategy filters in the OpenAlex request before
  pagination and the 100-record response bound
- [x] distinguish provider `total_count` from `returned_count`
- [x] expose `next_cursor` and `has_more`
- [x] add GUI controls for requesting subsequent cursor pages
- [ ] implement full automatic retrieval/import of all result pages
- [ ] complete an exact OpenAlex UI comparison when a reproducible UI URL or
  HAR is available

### UX

- visually separate the strategy form from search results
- add an executed-search information panel
- improve record presentation
- show citation counts
- show journal information
- show Open Access status
- expose PDF availability
- show abstracts
- add sorting
- improve the import workflow

### Technical debt

- hide inactive providers
- clean up search components
- refactor `SearchStrategyPage`
