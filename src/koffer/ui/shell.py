"""Dark application shell with S00–S21 foundations and transport."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut, QShowEvent
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
from koffer.domain.enums import JobState, JobType
from koffer.domain.errors import ApplicationError
from koffer.domain.file_operations import FileOperationPlan
from koffer.domain.ids import EntityId
from koffer.domain.query import SavedSearch
from koffer.jobs.progress import ProgressEvent
from koffer.ui.picker import DirectoryPicker, native_directory_picker
from koffer.ui.screens.about import AboutDiagnosticsScreen
from koffer.ui.screens.activity import ActivityCenterScreen
from koffer.ui.screens.collection_detail import CollectionDetailScreen
from koffer.ui.screens.collections import CollectionsScreen
from koffer.ui.screens.conflicts import ConflictsScreen
from koffer.ui.screens.import_review import ImportReviewScreen
from koffer.ui.screens.library import LibraryBrowserScreen
from koffer.ui.screens.maintenance import MaintenanceScreen
from koffer.ui.screens.metadata_editor import MetadataEditorScreen
from koffer.ui.screens.offline_recovery import OfflineRecoveryScreen
from koffer.ui.screens.render_export import RenderExportScreen
from koffer.ui.screens.sample_detail import SampleDetailScreen
from koffer.ui.screens.sample_preparation import SamplePreparationScreen
from koffer.ui.screens.settings_audio import SettingsAudioScreen
from koffer.ui.screens.settings_general import SettingsGeneralScreen
from koffer.ui.screens.settings_library import SettingsLibraryScreen
from koffer.ui.screens.similar_sounds import SimilarSoundsScreen
from koffer.ui.screens.source_detail import SourceDetailScreen
from koffer.ui.screens.sources import SourcesScreen
from koffer.ui.screens.suggestions_review import SuggestionsReviewScreen
from koffer.ui.screens.welcome import WelcomeScreen
from koffer.ui.tokens import CANVAS, SHELL_STYLESHEET
from koffer.ui.widgets.transport import TransportBar
from koffer.ui.window_geometry import WindowGeometryStore

WINDOW_TITLE = "Koffer"
CANVAS_COLOR = CANVAS

SCREEN_WELCOME = "S00"
SCREEN_LIBRARY = "S01"
SCREEN_COLLECTIONS = "S03"
SCREEN_COLLECTION_DETAIL = "S04"
SCREEN_SOURCES = "S05"
SCREEN_SOURCE_DETAIL = "S06"
SCREEN_SAMPLE_DETAIL = "S07"
SCREEN_SAMPLE_PREPARATION = "S08"
SCREEN_METADATA_EDITOR = "S09"
SCREEN_SUGGESTIONS = "S10"
SCREEN_SIMILAR_SOUNDS = "S11"
SCREEN_IMPORT_REVIEW = "S12"
SCREEN_CONFLICTS = "S13"
SCREEN_RENDER_EXPORT = "S14"
SCREEN_OFFLINE_RECOVERY = "S15"
SCREEN_ACTIVITY = "S16"
SCREEN_SETTINGS_GENERAL = "S17"
SCREEN_SETTINGS_LIBRARY = "S18"
SCREEN_SETTINGS_AUDIO = "S19"
SCREEN_MAINTENANCE = "S20"
SCREEN_ABOUT = "S21"


class _JobProgressBridge(QObject):
    progress = Signal(object)

    def publish(self, event: ProgressEvent) -> None:
        self.progress.emit(event)


class MainWindow(QMainWindow):
    """Composable main window; UI never owns SQL — services via AppContext."""

    def __init__(
        self,
        context: AppContext,
        *,
        directory_picker: DirectoryPicker | None = None,
        parent: QWidget | None = None,
        restore_geometry: bool = True,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._directory_picker = directory_picker or native_directory_picker
        self._current_screen = SCREEN_WELCOME
        self._library_nav_mode = "library"
        self._geometry_store = WindowGeometryStore(context.paths.config_dir)
        self._restore_geometry = restore_geometry
        self._geometry_applied = False

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(SHELL_STYLESHEET)

        shell = QWidget()
        shell.setObjectName("kofferShell")
        # Preserve Phase 0 smoke identity on the shell canvas.
        shell.setProperty("canvasColor", CANVAS_COLOR)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._top_bar = self._build_top_bar()
        layout.addWidget(self._top_bar)
        self._job_progress_bridge = _JobProgressBridge(self)
        self._job_progress_bridge.progress.connect(self._on_job_progress)
        context.scheduler.add_progress_listener(self._job_progress_bridge.publish)

        body = QWidget()
        body.setObjectName("kofferBody")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._nav = self._build_nav()
        body_layout.addWidget(self._nav)

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

        body_layout.addWidget(center, stretch=1)
        layout.addWidget(body, stretch=1)

        self._welcome = WelcomeScreen()
        self._library = LibraryBrowserScreen(context)
        self._collections = CollectionsScreen(context.collection_service)
        self._collection_detail = CollectionDetailScreen(context.collection_service)
        self._sources = SourcesScreen(context.source_service)
        self._source_detail = SourceDetailScreen(context.source_service)
        self._sample_detail = SampleDetailScreen(context.sample_service)
        self._sample_preparation = SamplePreparationScreen(context.preparation_service)
        self._metadata_editor = MetadataEditorScreen(context.metadata_service)
        self._suggestions = SuggestionsReviewScreen(context.analysis_service)
        self._similar_sounds = SimilarSoundsScreen(context.similarity_service)
        self._import_review = ImportReviewScreen(context.file_operation_service)
        self._conflicts = ConflictsScreen(context.file_operation_service)
        self._render_export = RenderExportScreen(context.preparation_service)
        self._offline_recovery = OfflineRecoveryScreen(context.recovery_service)
        self._activity = ActivityCenterScreen(context.scheduler)
        self._settings_general = SettingsGeneralScreen(context)
        self._settings_library = SettingsLibraryScreen(context)
        self._settings_audio = SettingsAudioScreen(context)
        self._maintenance = MaintenanceScreen(context)
        self._about = AboutDiagnosticsScreen(context)
        self._library_refresh_debounce = QTimer(self)
        self._library_refresh_debounce.setSingleShot(True)
        self._library_refresh_debounce.setInterval(250)
        self._library_refresh_debounce.timeout.connect(self._library.refresh)
        self._activity_refresh_debounce = QTimer(self)
        self._activity_refresh_debounce.setSingleShot(True)
        self._activity_refresh_debounce.setInterval(200)
        self._activity_refresh_debounce.timeout.connect(self._activity.refresh)

        self._stack.addWidget(self._welcome)
        self._stack.addWidget(self._library)
        self._stack.addWidget(self._collections)
        self._stack.addWidget(self._collection_detail)
        self._stack.addWidget(self._sources)
        self._stack.addWidget(self._source_detail)
        self._stack.addWidget(self._sample_detail)
        self._stack.addWidget(self._sample_preparation)
        self._stack.addWidget(self._metadata_editor)
        self._stack.addWidget(self._suggestions)
        self._stack.addWidget(self._similar_sounds)
        self._stack.addWidget(self._import_review)
        self._stack.addWidget(self._conflicts)
        self._stack.addWidget(self._render_export)
        self._stack.addWidget(self._offline_recovery)
        self._stack.addWidget(self._activity)
        self._stack.addWidget(self._settings_general)
        self._stack.addWidget(self._settings_library)
        self._stack.addWidget(self._settings_audio)
        self._stack.addWidget(self._maintenance)
        self._stack.addWidget(self._about)

        self._welcome.add_source_requested.connect(self._pick_and_add_source)
        self._welcome.directory_dropped.connect(self._add_source_path)
        self._sources.add_source_requested.connect(self._pick_and_add_source)
        self._sources.source_selected.connect(self._open_source_detail)
        self._source_detail.back_requested.connect(lambda: self.navigate(SCREEN_SOURCES))
        self._collections.collection_selected.connect(self._open_collection_detail)
        self._collection_detail.back_requested.connect(lambda: self.navigate(SCREEN_COLLECTIONS))
        self._library.selection_changed.connect(self._on_library_selection)
        self._library.open_sample_detail_requested.connect(self._open_sample_detail)
        self._library.prepare_requested.connect(self._open_sample_preparation)
        self._library.edit_metadata_requested.connect(self._open_metadata_editor)
        self._library.find_similar_requested.connect(self._open_similar_sounds)
        self._library.saved_searches_changed.connect(self._refresh_saved_search_nav)
        self._sample_detail.back_requested.connect(lambda: self.navigate(SCREEN_LIBRARY))
        self._sample_detail.edit_metadata_requested.connect(self._open_metadata_editor)
        self._sample_detail.prepare_requested.connect(self._open_sample_preparation)
        self._sample_detail.find_similar_requested.connect(self._open_similar_sounds)
        self._similar_sounds.back_requested.connect(lambda: self.navigate(SCREEN_SAMPLE_DETAIL))
        self._similar_sounds.preview_requested.connect(self._preview_similar_sample)
        self._sample_preparation.back_requested.connect(lambda: self.navigate(SCREEN_SAMPLE_DETAIL))
        self._sample_preparation.export_requested.connect(self._open_render_export)
        self._metadata_editor.back_requested.connect(lambda: self.navigate(SCREEN_SAMPLE_DETAIL))
        self._metadata_editor.execute_requested.connect(self._execute_metadata_plan)
        self._suggestions.back_requested.connect(lambda: self.navigate(SCREEN_LIBRARY))
        self._import_review.back_requested.connect(lambda: self.navigate(SCREEN_LIBRARY))
        self._import_review.resolve_conflicts_requested.connect(self._open_conflicts_from_review)
        self._import_review.execute_requested.connect(self._execute_import_plan)
        self._conflicts.back_requested.connect(lambda: self.navigate(SCREEN_IMPORT_REVIEW))
        self._conflicts.apply_requested.connect(self._return_from_conflicts)
        self._render_export.back_requested.connect(lambda: self.navigate(SCREEN_SAMPLE_PREPARATION))
        self._render_export.execute_requested.connect(self._execute_render_plan)
        self._settings_general.open_library_settings_requested.connect(
            lambda: self.navigate(SCREEN_SETTINGS_LIBRARY)
        )
        self._settings_general.open_audio_settings_requested.connect(
            lambda: self.navigate(SCREEN_SETTINGS_AUDIO)
        )

        self._build_menus()
        self._refresh_saved_search_nav()
        self._refresh_job_status()
        self._install_global_shortcuts()

        self.setCentralWidget(shell)
        # Geometry is applied on first showEvent so offscreen sizes stick.
        self._sync_initial_route()

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("kofferTopBar")
        bar.setFixedHeight(40)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(16)

        brand = QLabel("KOFFER")
        brand.setObjectName("topBarBrand")
        row.addWidget(brand)

        self._workspace_label = QLabel("Welcome")
        self._workspace_label.setObjectName("topBarWorkspace")
        row.addWidget(self._workspace_label)
        row.addStretch(1)

        self._job_status = QPushButton("IDLE")
        self._job_status.setObjectName("topBarActivityButton")
        self._job_status.setToolTip("Open Activity Center")
        self._job_status.clicked.connect(lambda: self.navigate(SCREEN_ACTIVITY))
        row.addWidget(self._job_status)

        status = QLabel("LOCAL")
        status.setObjectName("topBarStatus")
        status.setToolTip("Koffer core library features work locally and offline.")
        row.addWidget(status)
        return bar

    @Slot(object)
    def _on_job_progress(self, event: object) -> None:
        if not isinstance(event, ProgressEvent):
            return
        active_states = {
            JobState.QUEUED,
            JobState.RUNNING,
            JobState.CANCEL_REQUESTED,
        }
        if event.state in active_states:
            stage = (event.stage or "working").replace("_", " ").upper()
            if event.total is not None and event.total > 0:
                self._job_status.setText(f"{stage} {event.current}/{event.total}")
            else:
                self._job_status.setText(stage)
        else:
            self._refresh_job_status()

        try:
            job = self._context.scheduler.get(event.job_id)
        except ApplicationError:
            job = None
        if job is not None and job.type in {
            JobType.SOURCE_SCAN,
            JobType.TECHNICAL_PROBE,
            JobType.DETERMINISTIC_ANALYSIS,
        }:
            self._library_refresh_debounce.start()
            if job.type is JobType.SOURCE_SCAN:
                self._sources.refresh()
        self._activity_refresh_debounce.start()

    def _refresh_job_status(self) -> None:
        jobs = self._context.scheduler.list()
        active_states = {
            JobState.QUEUED,
            JobState.RUNNING,
            JobState.CANCEL_REQUESTED,
        }
        attention_states = {
            JobState.FAILED,
            JobState.COMPLETED_WITH_ERRORS,
            JobState.INTERRUPTED,
        }
        active = sum(job.state in active_states for job in jobs)
        attention = sum(job.state in attention_states for job in jobs)
        if attention:
            noun = "ISSUE" if attention == 1 else "ISSUES"
            self._job_status.setText(f"{attention} {noun}")
        elif active:
            noun = "JOB" if active == 1 else "JOBS"
            self._job_status.setText(f"{active} {noun}")
        else:
            self._job_status.setText("IDLE")

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setObjectName("kofferMenuBar")

        file_menu = menu_bar.addMenu("&File")
        add_source = QAction("Add Source…", self)
        add_source.setShortcut(QKeySequence("Ctrl+O"))
        add_source.triggered.connect(self._pick_and_add_source)
        file_menu.addAction(add_source)
        file_menu.addSeparator()
        settings = QAction("Settings", self)
        settings.setShortcut(QKeySequence("Ctrl+,"))
        settings.triggered.connect(lambda: self.navigate(SCREEN_SETTINGS_GENERAL))
        file_menu.addAction(settings)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        library_menu = menu_bar.addMenu("&Library")
        for label, callback in (
            ("All Samples", self._open_all_samples),
            ("Favourites", self._open_favourites),
            ("Recents", self._open_recents),
        ):
            action = QAction(label, self)
            action.triggered.connect(callback)
            library_menu.addAction(action)
        library_menu.addSeparator()
        for label, screen in (
            ("Collections", SCREEN_COLLECTIONS),
            ("Sources", SCREEN_SOURCES),
            ("Suggestions Review", SCREEN_SUGGESTIONS),
            ("Activity", SCREEN_ACTIVITY),
            ("Maintenance", SCREEN_MAINTENANCE),
        ):
            action = QAction(label, self)
            action.triggered.connect(
                lambda _checked=False, target=screen: self.navigate(target),
            )
            library_menu.addAction(action)

        view_menu = menu_bar.addMenu("&View")
        sidebar = QAction("Toggle Sidebar", self)
        sidebar.triggered.connect(
            lambda: self._nav.setVisible(not self._nav.isVisible()),
        )
        view_menu.addAction(sidebar)
        inspector = QAction("Toggle Inspector", self)
        inspector.triggered.connect(self._library.inspector.toggle_collapsed)
        view_menu.addAction(inspector)
        reset = QAction("Reset Pane Layout", self)
        reset.triggered.connect(lambda: self._library.splitter.setSizes([900, 340]))
        view_menu.addAction(reset)

        help_menu = menu_bar.addMenu("&Help")
        about = QAction("About & Diagnostics", self)
        about.triggered.connect(lambda: self.navigate(SCREEN_ABOUT))
        help_menu.addAction(about)

    def _open_all_samples(self) -> None:
        self._library_nav_mode = "library"
        self._library.show_all_samples()
        self.navigate(SCREEN_LIBRARY)

    def _open_favourites(self) -> None:
        self._library_nav_mode = "favourites"
        self._library.show_favourites()
        self.navigate(SCREEN_LIBRARY)

    def _open_recents(self) -> None:
        self._library_nav_mode = "recents"
        self._library.show_recents()
        self.navigate(SCREEN_LIBRARY)

    def _open_saved_search(self, saved: SavedSearch) -> None:
        self._library_nav_mode = f"saved:{saved.id}"
        self._library.show_saved_search(saved)
        self.navigate(SCREEN_LIBRARY)

    def _refresh_saved_search_nav(self) -> None:
        if not hasattr(self, "_saved_search_layout"):
            return
        while self._saved_search_layout.count():
            item = self._saved_search_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._saved_search_buttons.clear()

        saved_searches = self._context.search_service.list_saved_searches()
        if not saved_searches:
            empty = QLabel("No saved searches")
            empty.setObjectName("navEmptyText")
            self._saved_search_layout.addWidget(empty)
            return

        for saved in saved_searches:
            button = QPushButton(saved.name)
            button.setObjectName("savedSearchNavButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, item=saved: self._open_saved_search(item),
            )
            button.setProperty("savedSearchId", str(saved.id))
            self._saved_search_buttons.append(button)
            self._saved_search_layout.addWidget(button)

    def _update_top_bar(self) -> None:
        if self._current_screen == SCREEN_LIBRARY:
            label = self._library.view_title
        else:
            label = {
                SCREEN_WELCOME: "Welcome",
                SCREEN_COLLECTIONS: "Collections",
                SCREEN_COLLECTION_DETAIL: "Collection",
                SCREEN_SOURCES: "Sources",
                SCREEN_SOURCE_DETAIL: "Source",
                SCREEN_SAMPLE_DETAIL: "Sample Detail",
                SCREEN_SAMPLE_PREPARATION: "Prepare",
                SCREEN_METADATA_EDITOR: "Metadata",
                SCREEN_SUGGESTIONS: "Review",
                SCREEN_SIMILAR_SOUNDS: "Similar Sounds",
                SCREEN_IMPORT_REVIEW: "Organize",
                SCREEN_CONFLICTS: "Conflicts",
                SCREEN_RENDER_EXPORT: "Render / Export",
                SCREEN_OFFLINE_RECOVERY: "Recovery",
                SCREEN_ACTIVITY: "Activity",
                SCREEN_SETTINGS_GENERAL: "Settings",
                SCREEN_SETTINGS_LIBRARY: "Settings",
                SCREEN_SETTINGS_AUDIO: "Settings",
                SCREEN_MAINTENANCE: "Maintenance",
                SCREEN_ABOUT: "About & Diagnostics",
            }.get(self._current_screen, "Koffer")
        self._workspace_label.setText(label)

    def _install_global_shortcuts(self) -> None:
        """Default global shortcuts from docs/28."""
        self._focus_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._focus_search_shortcut.setObjectName("focusSearchShortcut")
        self._focus_search_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._focus_search_shortcut.activated.connect(self._focus_library_search)

        self._add_source_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self._add_source_shortcut.setObjectName("addSourceShortcut")
        self._add_source_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._add_source_shortcut.activated.connect(self._pick_and_add_source)

        self._settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self._settings_shortcut.setObjectName("settingsShortcut")
        self._settings_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._settings_shortcut.activated.connect(lambda: self.navigate(SCREEN_SETTINGS_GENERAL))

        self._activity_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        self._activity_shortcut.setObjectName("activityCenterShortcut")
        self._activity_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._activity_shortcut.activated.connect(lambda: self.navigate(SCREEN_ACTIVITY))

        self._quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self._quit_shortcut.setObjectName("quitShortcut")
        self._quit_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._quit_shortcut.activated.connect(self.close)

        self._escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._escape_shortcut.setObjectName("escapeShortcut")
        self._escape_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._escape_shortcut.activated.connect(self._handle_escape)

    @property
    def context(self) -> AppContext:
        return self._context

    @property
    def geometry_store(self) -> WindowGeometryStore:
        return self._geometry_store

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

    def metadata_editor(self) -> MetadataEditorScreen:
        return self._metadata_editor

    def suggestions_review(self) -> SuggestionsReviewScreen:
        return self._suggestions

    def sample_preparation(self) -> SamplePreparationScreen:
        return self._sample_preparation

    def render_export(self) -> RenderExportScreen:
        return self._render_export

    def current_screen_id(self) -> str:
        return self._current_screen

    def persist_geometry(self) -> None:
        """Save window and library pane geometry to XDG config."""
        self._geometry_store.save_window(self)
        self._geometry_store.save_splitter("library", self._library.splitter)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt API
        super().showEvent(event)
        if self._restore_geometry and not self._geometry_applied:
            self._apply_persisted_geometry()
            self._geometry_applied = True

    def _apply_persisted_geometry(self) -> None:
        self._geometry_store.restore_window(self)
        if not self._geometry_store.restore_splitter("library", self._library.splitter):
            sizes = self._geometry_store.load_splitter_sizes("library")
            if sizes:
                self._library.splitter.setSizes(sizes)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — Qt API
        self._context.scheduler.remove_progress_listener(self._job_progress_bridge.publish)
        self.persist_geometry()
        super().closeEvent(event)

    def open_file_operation_plan(self, plan: FileOperationPlan) -> None:
        """Present S12 with a planned Reference/Copy/Move operation."""
        self._import_review.show_plan(plan)
        self.navigate(SCREEN_IMPORT_REVIEW)

    def open_metadata_editor(self, sample_ids: list[EntityId]) -> None:
        """Present S09 for the given Sample ids."""
        self._metadata_editor.show_samples(sample_ids)
        self.navigate(SCREEN_METADATA_EDITOR)

    def open_suggestions_review(self) -> None:
        """Present S10 Suggestions Review inbox."""
        self.navigate(SCREEN_SUGGESTIONS)

    def open_similar_sounds(self, sample_id: EntityId, *, filename: str = "") -> None:
        """Present S11 Similar Sounds for the seed Sample."""
        self._similar_sounds.show_seed(sample_id, filename=filename)
        self.navigate(SCREEN_SIMILAR_SOUNDS)

    def open_sample_preparation(self, sample_id: EntityId) -> None:
        """Present S08 for the given Sample id."""
        self._sample_preparation.show_sample(sample_id)
        self.navigate(SCREEN_SAMPLE_PREPARATION)

    def open_render_export(self, sample_id: EntityId) -> None:
        """Present S14 for the given Sample id."""
        self._render_export.show_sample(sample_id)
        self.navigate(SCREEN_RENDER_EXPORT)

    def navigate(self, screen_id: str) -> None:
        mapping = {
            SCREEN_WELCOME: self._welcome,
            SCREEN_LIBRARY: self._library,
            SCREEN_COLLECTIONS: self._collections,
            SCREEN_COLLECTION_DETAIL: self._collection_detail,
            SCREEN_SOURCES: self._sources,
            SCREEN_SOURCE_DETAIL: self._source_detail,
            SCREEN_SAMPLE_DETAIL: self._sample_detail,
            SCREEN_SAMPLE_PREPARATION: self._sample_preparation,
            SCREEN_METADATA_EDITOR: self._metadata_editor,
            SCREEN_SUGGESTIONS: self._suggestions,
            SCREEN_SIMILAR_SOUNDS: self._similar_sounds,
            SCREEN_IMPORT_REVIEW: self._import_review,
            SCREEN_CONFLICTS: self._conflicts,
            SCREEN_RENDER_EXPORT: self._render_export,
            SCREEN_OFFLINE_RECOVERY: self._offline_recovery,
            SCREEN_ACTIVITY: self._activity,
            SCREEN_SETTINGS_GENERAL: self._settings_general,
            SCREEN_SETTINGS_LIBRARY: self._settings_library,
            SCREEN_SETTINGS_AUDIO: self._settings_audio,
            SCREEN_MAINTENANCE: self._maintenance,
            SCREEN_ABOUT: self._about,
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
        if screen_id == SCREEN_SAMPLE_PREPARATION:
            self._sample_preparation.refresh()
        if screen_id == SCREEN_METADATA_EDITOR:
            self._metadata_editor.refresh()
        if screen_id == SCREEN_SUGGESTIONS:
            self._suggestions.refresh()
        if screen_id == SCREEN_SIMILAR_SOUNDS:
            self._similar_sounds.refresh()
        if screen_id == SCREEN_IMPORT_REVIEW:
            self._import_review.refresh()
        if screen_id == SCREEN_CONFLICTS:
            self._conflicts.refresh()
        if screen_id == SCREEN_RENDER_EXPORT:
            self._render_export.refresh()
        if screen_id == SCREEN_OFFLINE_RECOVERY:
            self._offline_recovery.refresh()
        if screen_id == SCREEN_ACTIVITY:
            self._activity.refresh()
        if screen_id == SCREEN_SETTINGS_GENERAL:
            self._settings_general.refresh()
        if screen_id == SCREEN_SETTINGS_LIBRARY:
            self._settings_library.refresh()
        if screen_id == SCREEN_SETTINGS_AUDIO:
            self._settings_audio.refresh()
        if screen_id == SCREEN_MAINTENANCE:
            self._maintenance.refresh()
        if screen_id == SCREEN_ABOUT:
            self._about.refresh()
        self._stack.setCurrentWidget(widget)
        self._current_screen = screen_id
        self._update_nav_checked()
        self._update_top_bar()
        self._nav.setVisible(screen_id != SCREEN_WELCOME)
        self._transport.setVisible(screen_id != SCREEN_WELCOME)

    def _build_nav(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("kofferNavRail")
        rail.setFixedWidth(224)
        column = QVBoxLayout(rail)
        column.setContentsMargins(12, 16, 12, 16)
        column.setSpacing(6)

        self._nav_library = self._make_nav_button("Library", self._open_all_samples)
        column.addWidget(self._nav_library)

        self._nav_favourites = self._make_nav_button(
            "Favourites",
            self._open_favourites,
        )
        column.addWidget(self._nav_favourites)

        self._nav_recents = self._make_nav_button("Recents", self._open_recents)
        column.addWidget(self._nav_recents)

        self._nav_suggestions = self._make_nav_button(
            "Review", lambda: self.navigate(SCREEN_SUGGESTIONS)
        )
        column.addWidget(self._nav_suggestions)

        self._nav_collections = self._make_nav_button(
            "Collections", lambda: self.navigate(SCREEN_COLLECTIONS)
        )
        column.addWidget(self._nav_collections)

        saved_label = QLabel("SAVED SEARCHES")
        saved_label.setObjectName("navSectionLabel")
        column.addWidget(saved_label)
        saved_container = QWidget()
        saved_container.setObjectName("savedSearchNav")
        self._saved_search_layout = QVBoxLayout(saved_container)
        self._saved_search_buttons: list[QPushButton] = []
        self._saved_search_layout.setContentsMargins(0, 0, 0, 0)
        self._saved_search_layout.setSpacing(4)
        column.addWidget(saved_container)

        self._nav_sources = self._make_nav_button("Sources", lambda: self.navigate(SCREEN_SOURCES))
        column.addWidget(self._nav_sources)

        self._nav_activity = self._make_nav_button(
            "Activity", lambda: self.navigate(SCREEN_ACTIVITY)
        )
        column.addWidget(self._nav_activity)

        self._nav_settings = self._make_nav_button(
            "Settings", lambda: self.navigate(SCREEN_SETTINGS_GENERAL)
        )
        column.addWidget(self._nav_settings)

        column.addStretch(1)
        return rail

    def _make_nav_button(self, label: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.clicked.connect(callback)
        return button

    def _update_nav_checked(self) -> None:
        library_active = self._current_screen == SCREEN_LIBRARY
        self._nav_library.setChecked(library_active and self._library_nav_mode == "library")
        self._nav_favourites.setChecked(library_active and self._library_nav_mode == "favourites")
        self._nav_recents.setChecked(library_active and self._library_nav_mode == "recents")
        self._nav_collections.setChecked(
            self._current_screen in {SCREEN_COLLECTIONS, SCREEN_COLLECTION_DETAIL}
        )
        self._nav_sources.setChecked(self._current_screen in {SCREEN_SOURCES, SCREEN_SOURCE_DETAIL})
        self._nav_suggestions.setChecked(self._current_screen == SCREEN_SUGGESTIONS)
        self._nav_activity.setChecked(self._current_screen == SCREEN_ACTIVITY)
        self._nav_settings.setChecked(
            self._current_screen
            in {
                SCREEN_SETTINGS_GENERAL,
                SCREEN_SETTINGS_LIBRARY,
                SCREEN_SETTINGS_AUDIO,
                SCREEN_MAINTENANCE,
            }
        )

        saved_id = (
            self._library_nav_mode.removeprefix("saved:")
            if library_active and self._library_nav_mode.startswith("saved:")
            else ""
        )
        saved_button: QPushButton
        for saved_button in self._saved_search_buttons:
            saved_button.setChecked(saved_button.property("savedSearchId") == saved_id)

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

    def _open_metadata_editor(self, sample_id: object) -> None:
        if not isinstance(sample_id, str):
            sample_id = str(sample_id)
        self.open_metadata_editor([EntityId(sample_id)])

    def _open_sample_preparation(self, sample_id: object) -> None:
        if not isinstance(sample_id, str):
            sample_id = str(sample_id)
        self.open_sample_preparation(EntityId(sample_id))

    def _open_similar_sounds(self, sample_id: object) -> None:
        if not isinstance(sample_id, str):
            sample_id = str(sample_id)
        sid = EntityId(sample_id)
        detail = self._context.sample_service.get_detail(sid)
        self.open_similar_sounds(sid, filename=detail.sample.filename)

    def _preview_similar_sample(self, sample_id: object) -> None:
        if not isinstance(sample_id, str):
            sample_id = str(sample_id)
        sid = EntityId(sample_id)
        path = self._context.resolve_sample_media_path(sid)
        if path is None:
            return
        self._context.playback_service.load(sid, path)
        detail = self._context.sample_service.get_detail(sid)
        self._transport.set_selection(str(sid), detail.sample.filename)

    def _open_render_export(self, sample_id: object) -> None:
        if not isinstance(sample_id, str):
            sample_id = str(sample_id)
        self.open_render_export(EntityId(sample_id))

    def _execute_render_plan(self) -> None:
        plan = self._render_export.plan
        if plan is None:
            return
        try:
            job_id = self._context.preparation_service.execute_render(plan)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not start render", str(exc))
            return
        del job_id
        self.navigate(SCREEN_ACTIVITY)

    def _execute_metadata_plan(self) -> None:
        plan = self._metadata_editor.plan
        if plan is None:
            return
        try:
            job_id = self._context.metadata_service.execute(plan)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not execute metadata write", str(exc))
            return
        del job_id
        self.navigate(SCREEN_ACTIVITY)

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

    def trigger_focus_search_shortcut(self) -> None:
        """Activate the docs/28 Ctrl+F binding (deterministic offscreen path)."""
        self._focus_search_shortcut.activated.emit()

    def _handle_escape(self) -> None:
        if self._current_screen == SCREEN_LIBRARY and self._library.clear_search_or_defocus():
            return
        if self._current_screen in {
            SCREEN_SAMPLE_DETAIL,
            SCREEN_SAMPLE_PREPARATION,
            SCREEN_METADATA_EDITOR,
            SCREEN_SIMILAR_SOUNDS,
            SCREEN_IMPORT_REVIEW,
            SCREEN_CONFLICTS,
            SCREEN_RENDER_EXPORT,
            SCREEN_SOURCE_DETAIL,
            SCREEN_COLLECTION_DETAIL,
            SCREEN_SUGGESTIONS,
            SCREEN_SETTINGS_LIBRARY,
            SCREEN_SETTINGS_AUDIO,
        }:
            if self._current_screen == SCREEN_SOURCE_DETAIL:
                self.navigate(SCREEN_SOURCES)
            elif self._current_screen == SCREEN_COLLECTION_DETAIL:
                self.navigate(SCREEN_COLLECTIONS)
            elif self._current_screen in {SCREEN_SETTINGS_LIBRARY, SCREEN_SETTINGS_AUDIO}:
                self.navigate(SCREEN_SETTINGS_GENERAL)
            elif self._current_screen in {
                SCREEN_SAMPLE_PREPARATION,
                SCREEN_METADATA_EDITOR,
                SCREEN_SIMILAR_SOUNDS,
                SCREEN_RENDER_EXPORT,
            }:
                self.navigate(SCREEN_SAMPLE_DETAIL)
            elif self._current_screen == SCREEN_CONFLICTS:
                self.navigate(SCREEN_IMPORT_REVIEW)
            else:
                self.navigate(SCREEN_LIBRARY)

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
