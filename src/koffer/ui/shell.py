"""Dark application shell with navigation, S00–S07/S12/S13/S16 foundations, transport, shortcuts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.domain.errors import ApplicationError
from koffer.domain.file_operations import FileOperationPlan
from koffer.domain.ids import EntityId
from koffer.ui.picker import DirectoryPicker, native_directory_picker
from koffer.ui.screens.activity import ActivityCenterScreen
from koffer.ui.screens.collection_detail import CollectionDetailScreen
from koffer.ui.screens.collections import CollectionsScreen
from koffer.ui.screens.conflicts import ConflictsScreen
from koffer.ui.screens.import_review import ImportReviewScreen
from koffer.ui.screens.library import LibraryBrowserScreen
from koffer.ui.screens.sample_detail import SampleDetailScreen
from koffer.ui.screens.source_detail import SourceDetailScreen
from koffer.ui.screens.sources import SourcesScreen
from koffer.ui.screens.welcome import WelcomeScreen
from koffer.ui.tokens import CANVAS, CLAY, SHELL_STYLESHEET
from koffer.ui.widgets.transport import TransportBar

WINDOW_TITLE = "Koffer"
CANVAS_COLOR = CANVAS

SCREEN_WELCOME = "S00"
SCREEN_LIBRARY = "S01"
SCREEN_COLLECTIONS = "S03"
SCREEN_COLLECTION_DETAIL = "S04"
SCREEN_SOURCES = "S05"
SCREEN_SOURCE_DETAIL = "S06"
SCREEN_SAMPLE_DETAIL = "S07"
SCREEN_IMPORT_REVIEW = "S12"
SCREEN_CONFLICTS = "S13"
SCREEN_ACTIVITY = "S16"


class MainWindow(QMainWindow):
    """Composable main window; UI never owns SQL — services via AppContext."""

    def __init__(
        self,
        context: AppContext,
        *,
        directory_picker: DirectoryPicker | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._directory_picker = directory_picker or native_directory_picker
        self._current_screen = SCREEN_WELCOME

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1440, 900)
        self.setStyleSheet(SHELL_STYLESHEET)

        shell = QWidget()
        shell.setObjectName("kofferShell")
        # Preserve Phase 0 smoke identity on the shell canvas.
        shell.setProperty("canvasColor", CANVAS_COLOR)
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._nav = self._build_nav()
        layout.addWidget(self._nav)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setObjectName("kofferStack")
        center_layout.addWidget(self._stack, stretch=1)

        self._transport = TransportBar(context.playback_service)
        self._transport.bind_selection_loader(self._load_playback_from_library)
        center_layout.addWidget(self._transport)

        layout.addWidget(center, stretch=1)

        self._welcome = WelcomeScreen()
        self._library = LibraryBrowserScreen(context)
        self._collections = CollectionsScreen(context.collection_service)
        self._collection_detail = CollectionDetailScreen(context.collection_service)
        self._sources = SourcesScreen(context.source_service)
        self._source_detail = SourceDetailScreen(context.source_service)
        self._sample_detail = SampleDetailScreen(context.sample_service)
        self._import_review = ImportReviewScreen(context.file_operation_service)
        self._conflicts = ConflictsScreen(context.file_operation_service)
        self._activity = ActivityCenterScreen(context.scheduler)

        self._stack.addWidget(self._welcome)
        self._stack.addWidget(self._library)
        self._stack.addWidget(self._collections)
        self._stack.addWidget(self._collection_detail)
        self._stack.addWidget(self._sources)
        self._stack.addWidget(self._source_detail)
        self._stack.addWidget(self._sample_detail)
        self._stack.addWidget(self._import_review)
        self._stack.addWidget(self._conflicts)
        self._stack.addWidget(self._activity)

        self._welcome.add_source_requested.connect(self._pick_and_add_source)
        self._welcome.directory_dropped.connect(self._add_source_path)
        self._sources.add_source_requested.connect(self._pick_and_add_source)
        self._sources.source_selected.connect(self._open_source_detail)
        self._source_detail.back_requested.connect(lambda: self.navigate(SCREEN_SOURCES))
        self._collections.collection_selected.connect(self._open_collection_detail)
        self._collection_detail.back_requested.connect(lambda: self.navigate(SCREEN_COLLECTIONS))
        self._library.selection_changed.connect(self._on_library_selection)
        self._library.open_sample_detail_requested.connect(self._open_sample_detail)
        self._sample_detail.back_requested.connect(lambda: self.navigate(SCREEN_LIBRARY))
        self._import_review.back_requested.connect(lambda: self.navigate(SCREEN_LIBRARY))
        self._import_review.resolve_conflicts_requested.connect(self._open_conflicts_from_review)
        self._import_review.execute_requested.connect(self._execute_import_plan)
        self._conflicts.back_requested.connect(lambda: self.navigate(SCREEN_IMPORT_REVIEW))
        self._conflicts.apply_requested.connect(self._return_from_conflicts)

        self._focus_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._focus_search_shortcut.setObjectName("focusSearchShortcut")
        self._focus_search_shortcut.activated.connect(self._focus_library_search)

        self._activity_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        self._activity_shortcut.setObjectName("activityCenterShortcut")
        self._activity_shortcut.activated.connect(lambda: self.navigate(SCREEN_ACTIVITY))

        self.setCentralWidget(shell)
        self._sync_initial_route()

    @property
    def context(self) -> AppContext:
        return self._context

    @property
    def transport(self) -> TransportBar:
        return self._transport

    @property
    def library(self) -> LibraryBrowserScreen:
        return self._library

    @property
    def collections(self) -> CollectionsScreen:
        return self._collections

    @property
    def collection_detail(self) -> CollectionDetailScreen:
        return self._collection_detail

    @property
    def activity(self) -> ActivityCenterScreen:
        return self._activity

    @property
    def import_review(self) -> ImportReviewScreen:
        return self._import_review

    @property
    def conflicts(self) -> ConflictsScreen:
        return self._conflicts

    def current_screen_id(self) -> str:
        return self._current_screen

    def open_file_operation_plan(self, plan: FileOperationPlan) -> None:
        """Present S12 with a planned Reference/Copy/Move operation."""
        self._import_review.show_plan(plan)
        self.navigate(SCREEN_IMPORT_REVIEW)

    def navigate(self, screen_id: str) -> None:
        mapping = {
            SCREEN_WELCOME: self._welcome,
            SCREEN_LIBRARY: self._library,
            SCREEN_COLLECTIONS: self._collections,
            SCREEN_COLLECTION_DETAIL: self._collection_detail,
            SCREEN_SOURCES: self._sources,
            SCREEN_SOURCE_DETAIL: self._source_detail,
            SCREEN_SAMPLE_DETAIL: self._sample_detail,
            SCREEN_IMPORT_REVIEW: self._import_review,
            SCREEN_CONFLICTS: self._conflicts,
            SCREEN_ACTIVITY: self._activity,
        }
        widget = mapping.get(screen_id)
        if widget is None:
            return
        if screen_id == SCREEN_LIBRARY:
            self._library.refresh()
        if screen_id == SCREEN_COLLECTIONS:
            self._collections.refresh()
        if screen_id == SCREEN_COLLECTION_DETAIL:
            self._collection_detail.refresh()
        if screen_id == SCREEN_SOURCES:
            self._sources.refresh()
        if screen_id == SCREEN_SOURCE_DETAIL:
            self._source_detail.refresh()
        if screen_id == SCREEN_SAMPLE_DETAIL:
            self._sample_detail.refresh()
        if screen_id == SCREEN_IMPORT_REVIEW:
            self._import_review.refresh()
        if screen_id == SCREEN_CONFLICTS:
            self._conflicts.refresh()
        if screen_id == SCREEN_ACTIVITY:
            self._activity.refresh()
        self._stack.setCurrentWidget(widget)
        self._current_screen = screen_id
        self._update_nav_checked()
        self._nav.setVisible(screen_id != SCREEN_WELCOME)

    def _build_nav(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("kofferNavRail")
        rail.setFixedWidth(224)
        column = QVBoxLayout(rail)
        column.setContentsMargins(12, 16, 12, 16)
        column.setSpacing(8)

        brand = QLabel("Koffer")
        brand.setStyleSheet(f"color: {CLAY}; font-size: 18px; font-weight: 700;")
        column.addWidget(brand)

        self._nav_library = QPushButton("Library")
        self._nav_library.setObjectName("navButton")
        self._nav_library.setCheckable(True)
        self._nav_library.clicked.connect(lambda: self.navigate(SCREEN_LIBRARY))
        column.addWidget(self._nav_library)

        self._nav_collections = QPushButton("Collections")
        self._nav_collections.setObjectName("navButton")
        self._nav_collections.setCheckable(True)
        self._nav_collections.clicked.connect(lambda: self.navigate(SCREEN_COLLECTIONS))
        column.addWidget(self._nav_collections)

        self._nav_sources = QPushButton("Sources")
        self._nav_sources.setObjectName("navButton")
        self._nav_sources.setCheckable(True)
        self._nav_sources.clicked.connect(lambda: self.navigate(SCREEN_SOURCES))
        column.addWidget(self._nav_sources)

        self._nav_activity = QPushButton("Activity")
        self._nav_activity.setObjectName("navButton")
        self._nav_activity.setCheckable(True)
        self._nav_activity.clicked.connect(lambda: self.navigate(SCREEN_ACTIVITY))
        column.addWidget(self._nav_activity)

        column.addStretch(1)
        return rail

    def _update_nav_checked(self) -> None:
        self._nav_library.setChecked(self._current_screen == SCREEN_LIBRARY)
        self._nav_collections.setChecked(
            self._current_screen in {SCREEN_COLLECTIONS, SCREEN_COLLECTION_DETAIL}
        )
        self._nav_sources.setChecked(self._current_screen in {SCREEN_SOURCES, SCREEN_SOURCE_DETAIL})
        self._nav_activity.setChecked(self._current_screen == SCREEN_ACTIVITY)

    def _sync_initial_route(self) -> None:
        if self._context.source_service.list():
            self.navigate(SCREEN_LIBRARY)
        else:
            self.navigate(SCREEN_WELCOME)

    def _pick_and_add_source(self) -> None:
        path = self._directory_picker(self)
        if path is None:
            return
        self._add_source_path(path)

    def _add_source_path(self, path: object) -> None:
        if not isinstance(path, Path):
            path = Path(str(path))
        try:
            source = self._context.source_service.add_source(path)
            # Background scan; UI stays responsive.
            self._context.source_service.scan(source.id)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not add Source", str(exc))
            return
        # First-run success exits toward library/sources workspace.
        self.navigate(SCREEN_LIBRARY)
        self._sources.refresh()

    def _open_source_detail(self, source_id: object) -> None:
        if not isinstance(source_id, str):
            source_id = str(source_id)
        self._source_detail.show_source(EntityId(source_id))
        self.navigate(SCREEN_SOURCE_DETAIL)

    def _open_collection_detail(self, collection_id: object) -> None:
        if not isinstance(collection_id, str):
            collection_id = str(collection_id)
        self._collection_detail.show_collection(EntityId(collection_id))
        self.navigate(SCREEN_COLLECTION_DETAIL)

    def _open_sample_detail(self, sample_id: object) -> None:
        if not isinstance(sample_id, str):
            sample_id = str(sample_id)
        self._sample_detail.show_sample(EntityId(sample_id))
        self.navigate(SCREEN_SAMPLE_DETAIL)

    def _open_conflicts_from_review(self) -> None:
        plan = self._import_review.plan
        if plan is None:
            return
        self._conflicts.show_plan(plan)
        self.navigate(SCREEN_CONFLICTS)

    def _return_from_conflicts(self) -> None:
        plan = self._conflicts.plan
        if plan is not None:
            self._import_review.show_plan(plan)
        self.navigate(SCREEN_IMPORT_REVIEW)

    def _execute_import_plan(self) -> None:
        plan = self._import_review.plan
        if plan is None:
            return
        try:
            job_id = self._context.file_operation_service.execute(plan)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not execute plan", str(exc))
            return
        del job_id
        self.navigate(SCREEN_ACTIVITY)

    def _focus_library_search(self) -> None:
        if self._current_screen != SCREEN_LIBRARY:
            self.navigate(SCREEN_LIBRARY)
        self._library.focus_search()

    def focus_library_search(self) -> None:
        """Public Ctrl+F target used by shortcut and tests."""
        self._focus_library_search()

    def _on_library_selection(self, sample_id: object, name: object) -> None:
        sid = None if sample_id is None else str(sample_id)
        self._transport.set_selection(sid, str(name) if name else "")

    def _load_playback_from_library(self) -> None:
        self._library.load_selection_into_playback()


def create_main_window(
    context: AppContext | None = None,
    *,
    directory_picker: DirectoryPicker | None = None,
) -> MainWindow:
    """Create the Phase 5 shell; builds a default AppContext when omitted."""
    ctx = context or AppContext.open_default()
    return MainWindow(ctx, directory_picker=directory_picker)
