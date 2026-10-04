# 27. Service and Interface Contracts

## Purpose

This chapter fixes the boundaries an implementation agent can rely on. Concrete class names may vary slightly, but responsibilities and call semantics must remain recognizable.

## Common result model

Service methods that can fail for expected reasons return or raise typed application errors described in chapter 16. UI never parses exception strings to decide behavior.

Long-running calls return a Job ID immediately.

## SourceService

Required operations:

~~~python
add_source(path: Path, display_name: str | None = None) -> Source
remove_source(source_id: UUID) -> None
set_enabled(source_id: UUID, enabled: bool) -> None
update_exclusions(source_id: UUID, rules: list[ExclusionRule]) -> ExclusionPreview
scan(source_id: UUID, mode: ScanMode = INCREMENTAL) -> JobId
get(source_id: UUID) -> Source
list() -> list[Source]
~~~

Removing a Source removes Koffer indexing state according to explicit UI confirmation but never deletes its directory/audio.

## SearchService

~~~python
search(query: SampleQuery, page: PageRequest) -> Page[SampleRow]
count(query: SampleQuery) -> int
save_search(name: str, query: SampleQuery) -> SavedSearch
update_saved_search(id: UUID, ...) -> SavedSearch
delete_saved_search(id: UUID) -> None
~~~

SampleQuery is a typed versioned representation of S02 filters.

## CollectionService

~~~python
create(name: str, description: str | None = None) -> Collection
update(id: UUID, ...) -> Collection
delete(id: UUID) -> None
add_samples(collection_id: UUID, sample_ids: list[UUID]) -> None
remove_samples(collection_id: UUID, sample_ids: list[UUID]) -> None
reorder(collection_id: UUID, ordered_sample_ids: list[UUID]) -> None
~~~

No method mutates audio files.

## SampleService

~~~python
get_detail(sample_id: UUID) -> SampleDetail
set_favorite(sample_id: UUID, favorite: bool) -> None
set_user_tags(sample_id: UUID, tags: list[str]) -> None
set_classifications(sample_id: UUID, changes: ClassificationPatch) -> None
reveal_path(sample_id: UUID) -> Path
~~~

## PlaybackService

Event-driven adapter:

~~~python
load(sample_id: UUID, path: Path) -> None
play() -> None
pause() -> None
stop() -> None
seek(position_ms: int) -> None
set_loop(start_ms: int | None, end_ms: int | None) -> None
set_gain_db(gain_db: float) -> None
~~~

Signals/events:
- state_changed;
- position_changed;
- duration_changed;
- loaded_sample_changed;
- error.

## FileOperationService

Two-step API: plan, then execute.

~~~python
plan_reference(sample_ids, ...) -> FileOperationPlan
plan_copy(sample_ids, destination, conflict_policy=None) -> FileOperationPlan
plan_move(sample_ids, destination, conflict_policy=None) -> FileOperationPlan
execute(plan: FileOperationPlan) -> JobId
~~~

Execution refuses an outdated plan if source/destination fingerprints materially changed after review.

## MetadataService

~~~python
read_capabilities(sample_id: UUID) -> MetadataCapabilities
get_editor_state(sample_ids: list[UUID]) -> MetadataEditState
plan_write(request: MetadataWriteRequest) -> MetadataWritePlan
execute(plan: MetadataWritePlan) -> JobId
~~~

Targets are explicit enum values:
- UPDATE_ORIGINAL;
- WRITE_TO_COPY.

## PreparationService

~~~python
get_recipe(sample_id: UUID) -> PreparationRecipe
save_recipe(sample_id: UUID, recipe: PreparationRecipe) -> None
reset_recipe(sample_id: UUID) -> None
create_preview(sample_id: UUID, recipe: PreparationRecipe) -> PreviewHandle
plan_render(sample_id: UUID, recipe: PreparationRecipe, output: RenderOptions) -> RenderPlan
execute_render(plan: RenderPlan) -> JobId
~~~

## AnalysisService

~~~python
queue_for_sample(sample_id: UUID, depth: AnalysisDepth) -> JobId
queue_for_source(source_id: UUID, depth: AnalysisDepth) -> JobId
accept_suggestion(id: UUID, edited_value: str | None = None) -> None
reject_suggestion(id: UUID) -> None
batch_review(actions: list[SuggestionAction]) -> None
get_analysis_state(sample_id: UUID) -> AnalysisState
~~~

Accept creates/updates confirmed classification and retains Suggestion provenance.

## SimilarityService

~~~python
ensure_embedding(sample_id: UUID) -> JobId | None
find_similar(sample_id: UUID, limit: int, filters: SampleQuery | None = None) -> list[SimilarityResult]
rebuild_index() -> JobId
status() -> SimilarityStatus
~~~

If provider/model unavailable, return a typed ModelUnavailable condition used by S11.

## MaintenanceService

~~~python
backup(destination: Path) -> JobId
restore(backup_path: Path) -> JobId
verify_database(deep: bool = False) -> JobId
rebuild_filesystem_index() -> JobId
rebuild_waveforms() -> JobId
rebuild_analysis() -> JobId
rebuild_similarity() -> JobId
clear_cache(categories: set[CacheCategory]) -> JobId
~~~

## JobScheduler

~~~python
submit(spec: JobSpec) -> JobId
cancel(job_id: JobId) -> None
pause(job_id: JobId) -> None
resume(job_id: JobId) -> None
get(job_id: JobId) -> Job
list(filter: JobFilter) -> list[Job]
~~~

Pause may raise UnsupportedOperation for Job types that cannot safely pause.

## Repository contracts

Repositories expose transactional CRUD/query semantics but no Qt types.

A service can open a transaction scope and use multiple repositories atomically.

## UI binding

Qt screen/view-model code depends on service interfaces and typed read models such as:
- SampleRow;
- SampleDetail;
- SourceSummary;
- JobSummary;
- CollectionSummary.

Do not bind QTableView directly to arbitrary SQL.

## Stability

Tests should mock/fake these boundaries, not internal helper functions. This keeps Orders independently implementable without encouraging cross-layer coupling.
