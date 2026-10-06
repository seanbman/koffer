"""Paged Sample table model for S01 — fetches windows via SearchService only."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex, Qt

from koffer.domain.query import (
    DEFAULT_PAGE_LIMIT,
    PageRequest,
    SampleQuery,
    SampleRow,
    SortDirection,
    SortField,
    SortSpec,
)
from koffer.services.search import SearchService

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("name", "Name"),
    ("sample_type", "Sample Type"),
    ("instrument_source", "Instrument"),
    ("bpm", "BPM"),
    ("key", "Key"),
    ("duration_ms", "Duration"),
    ("extension", "Format"),
    ("availability", "Availability"),
)

_SORTABLE_COLUMNS: dict[int, SortField] = {
    0: SortField.NAME,
    1: SortField.SAMPLE_TYPE,
    2: SortField.INSTRUMENT_SOURCE,
    3: SortField.BPM,
    4: SortField.KEY,
    5: SortField.DURATION,
    6: SortField.EXTENSION,
    7: SortField.AVAILABILITY,
}

_Index = QModelIndex | QPersistentModelIndex
_INVALID_INDEX = QModelIndex()


class SampleTableModel(QAbstractTableModel):
    """QAbstractTableModel that pages SampleRow windows; never loads the full corpus."""

    def __init__(
        self,
        search_service: SearchService,
        *,
        page_size: int = DEFAULT_PAGE_LIMIT,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._search = search_service
        self._page_size = max(1, int(page_size))
        self._query = SampleQuery()
        self._total = 0
        # page_index -> tuple of SampleRow for that page window
        self._pages: dict[int, tuple[SampleRow, ...]] = {}
        self._fetch_count = 0

    @property
    def query(self) -> SampleQuery:
        return self._query

    @property
    def fetch_count(self) -> int:
        """Number of SearchService.search calls (tests: proves paging, not full load)."""
        return self._fetch_count

    @property
    def cached_row_count(self) -> int:
        """Rows currently held in the page cache."""
        return sum(len(page) for page in self._pages.values())

    def set_query(self, query: SampleQuery) -> None:
        """Replace active query and drop cached pages."""
        self.beginResetModel()
        self._query = query
        self._pages.clear()
        self._total = self._search.count(query)
        self.endResetModel()

    def set_sort(self, field: SortField, direction: SortDirection = SortDirection.ASC) -> None:
        """Update sort and refresh."""
        self.set_query(
            SampleQuery(
                version=self._query.version,
                text=self._query.text,
                filters=self._query.filters,
                sort=SortSpec(field=field, direction=direction),
            )
        )

    def refresh(self) -> None:
        """Re-count and clear cache for the current query."""
        self.set_query(self._query)

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        """Sort a visible browser column through SearchService, preserving paging."""
        field = _SORTABLE_COLUMNS.get(column)
        if field is None:
            return
        direction = (
            SortDirection.ASC
            if order == Qt.SortOrder.AscendingOrder
            else SortDirection.DESC
        )
        if self._query.sort.field == field and self._query.sort.direction == direction:
            return
        self.set_sort(field, direction)

    def rowCount(self, parent: _Index = _INVALID_INDEX) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return self._total

    def columnCount(self, parent: _Index = _INVALID_INDEX) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(_COLUMNS):
            return _COLUMNS[section][1]
        return None

    def data(  # noqa: N802
        self,
        index: _Index,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if not index.isValid() or role != int(Qt.ItemDataRole.DisplayRole):
            return None
        row = self._row_at(index.row())
        if row is None:
            return None
        key = _COLUMNS[index.column()][0]
        return _display_value(row, key)

    def sample_id_at(self, row: int) -> str | None:
        item = self._row_at(row)
        return None if item is None else str(item.id)

    def sample_row_at(self, row: int) -> SampleRow | None:
        """Return the SampleRow for a table row index (paged fetch)."""
        return self._row_at(row)

    def _row_at(self, row: int) -> SampleRow | None:
        if row < 0 or row >= self._total:
            return None
        page_index = row // self._page_size
        if page_index not in self._pages:
            self._fetch_page(page_index)
        page = self._pages.get(page_index)
        if page is None:
            return None
        offset_in_page = row % self._page_size
        if offset_in_page >= len(page):
            return None
        return page[offset_in_page]

    def _fetch_page(self, page_index: int) -> None:
        offset = page_index * self._page_size
        page = self._search.search(
            self._query,
            PageRequest(offset=offset, limit=self._page_size),
        )
        self._fetch_count += 1
        self._pages[page_index] = page.items
        # Keep a small window around the requested page to bound memory.
        keep = {page_index - 1, page_index, page_index + 1}
        for key in list(self._pages):
            if key not in keep:
                del self._pages[key]


def _display_value(row: SampleRow, key: str) -> str:
    if key == "name":
        return row.name
    if key == "sample_type":
        return row.sample_type or ""
    if key == "instrument_source":
        return row.instrument_source or ""
    if key == "bpm":
        return "" if row.bpm is None else f"{row.bpm:g}"
    if key == "key":
        return row.key or ""
    if key == "duration_ms":
        if row.duration_ms is None:
            return ""
        seconds = row.duration_ms / 1000.0
        return f"{seconds:.2f}s"
    if key == "extension":
        return row.extension
    if key == "availability":
        return str(row.availability)
    return ""
