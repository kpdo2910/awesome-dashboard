"""Qt settings dialog (Tools → Awesome Dashboard Settings…, or the dashboard gear).

macOS System Settings layout: a left nav with colored icon squares, and pages
built from grouped inset cards.
"""

from aqt import mw
from aqt.qt import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSize,
    QSpinBox,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..core import conf
from ..core.translations import (
    anki_language_code,
    available_languages,
    date_input_format,
    fmt_int,
    tr,
)

HOMEPAGE = "https://github.com/kpdo2910/awesome-dashboard"
ANKIWEB_CODE = "1243176816"
ANKIWEB_PAGE = f"https://ankiweb.net/shared/info/{ANKIWEB_CODE}"


def _addon_meta() -> dict:
    """Version and package read from manifest.json, plus Anki's own version.

    Reading the manifest keeps the About page honest: it shows what actually
    shipped rather than a constant someone has to remember to bump twice.
    """
    meta = {"version": "—", "package": "—", "anki": "—"}
    try:
        import json
        import os

        from ..core import paths

        path = os.path.join(paths.addon_root(), "manifest.json")
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        meta["version"] = str(manifest.get("human_version") or "—")
        meta["package"] = str(manifest.get("package") or "—")
    except Exception:
        pass
    try:
        import anki.buildinfo

        meta["anki"] = str(anki.buildinfo.version)
    except Exception:
        pass
    return meta


class _DeckResetDialog(QDialog):
    """Deck picker for the progress reset, with each deck's card count."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("reset_pick_title"))
        self.setModal(True)
        self.setMinimumWidth(430)
        try:
            from . import qt_theme

            self.setStyleSheet(qt_theme.settings_dialog_qss())
        except Exception:
            pass

        self._decks = []
        self.deck_list = QListWidget()
        self.deck_list.setObjectName("awdEventsList")
        try:
            nodes = list(mw.col.sched.deck_due_tree().children)
        except Exception:
            nodes = []
        for node in nodes:
            did = int(node.deck_id)
            try:
                count = len(mw.col.decks.cids(did, children=True))
            except Exception:
                count = 0
            self._decks.append(did)
            self.deck_list.addItem(f"{node.name} — {fmt_int(count)} {tr('cards_unit')}")
            item = self.deck_list.item(self.deck_list.count() - 1)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

        hint = QLabel(tr("reset_pick_hint"))
        hint.setObjectName("awdRowSub")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("reset"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(self.deck_list, 1)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def picked(self) -> list:
        """Deck ids the user ticked — empty if they cancelled or ticked none."""
        if not self.exec():
            return []
        chosen = [
            self._decks[i]
            for i in range(self.deck_list.count())
            if self.deck_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not chosen:
            from aqt.utils import showInfo

            showInfo(tr("reset_pick_none"), parent=self, title="Awesome Dashboard")
        return chosen


def _make_date_edit(initial_days_ahead: int = 30) -> QDateEdit:
    """A themed date picker: locale date order, Monday-first, no clutter."""
    date_edit = QDateEdit(QDate.currentDate().addDays(initial_days_ahead))
    date_edit.setCalendarPopup(True)
    date_edit.setDisplayFormat(date_input_format())
    try:
        from aqt.qt import QCalendarWidget

        calendar = date_edit.calendarWidget()
        if calendar:
            calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
            calendar.setVerticalHeaderFormat(
                QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
            )
            calendar.setGridVisible(False)
    except Exception:
        pass
    return date_edit


class _EventDialog(QDialog):
    """Small popup opened by the events list's + button."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("add_event_title"))
        self.setModal(True)
        self.setMinimumWidth(320)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("event_name_placeholder"))
        self.date_edit = _make_date_edit()
        form.addRow(tr("event_name_label"), self.name_edit)
        form.addRow(tr("event_date_label"), self.date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("add_event"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.name_edit.setFocus()

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        super().accept()

    def result_event(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
        }


def _run_deck_action(kind: str, did: int) -> None:
    """Delegate to the deck browser's own handlers — the exact code paths the
    dashboard's ⋮ menu used before these moved into Settings."""
    browser = getattr(mw, "deckBrowser", None)
    if browser is None:
        return
    try:
        # _delete resolves the deck's name through _render_data.tree, which is
        # stale (or missing) unless the dashboard rendered recently.
        from ..screens import dashboard

        browser._render_data = dashboard._render_data_for(
            mw.col.sched.deck_due_tree()
        )
    except Exception:
        pass
    handler = {
        "rename": getattr(browser, "_rename", None),
        "options": getattr(browser, "_options", None),
        "export": getattr(browser, "_export", None),
        "delete": getattr(browser, "_delete", None),
    }.get(kind)
    if handler is None:
        return
    try:
        from anki.decks import DeckId

        handler(DeckId(did))
    except Exception as e:
        from aqt.utils import showWarning

        showWarning(f"{tr('deck_action_failed')}\n\n{e}", parent=mw)


def _reload_current_screen() -> None:
    try:
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        elif mw.state == "overview":
            mw.overview.refresh()
        mw.toolbar.draw()
    except Exception:
        pass


def _offer_anki_language(code: str, previous: str) -> None:
    """Put Anki itself into the language just picked here, or undo the pick.

    Anki reads its UI language only at startup, so this takes the same two steps
    Preferences does: `pm.setLang` then a restart. Declining rolls the add-on back
    to `previous`, rather than leaving the two speaking different languages.
    """
    from aqt.utils import askUser, showWarning

    target = anki_language_code(code)
    if not target:
        return
    try:
        if mw.pm.meta.get("defaultLang", "") == target:
            return
    except Exception:
        return

    language = dict(available_languages()).get(code, code)
    if askUser(
        tr("anki_lang_prompt", language=language),
        parent=mw,
        title="Awesome Dashboard",
    ):
        try:
            mw.pm.setLang(target)
        except Exception as e:
            showWarning(f"{tr('anki_lang_failed')}\n\n{e}", parent=mw)
        else:
            from .bridge import _restart_anki

            _restart_anki()
            return

    conf.set_value("language", previous)
    _reload_current_screen()


THEME_ORDER = ["glass", "terracotta", "matcha", "ajisai", "sakura", "sumi"]
SIDEBAR_ORDER = ["full", "compact", "hidden"]


def _anki_theme_map():
    """{"system"|"light"|"dark": aqt Theme member} — None if the API is absent."""
    try:
        from aqt.theme import Theme

        return {
            "system": Theme.FOLLOW_SYSTEM,
            "light": Theme.LIGHT,
            "dark": Theme.DARK,
        }
    except Exception:
        return None


class AwdSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setObjectName("awdSettings")
        self.setWindowTitle("Awesome Dashboard")
        self.resize(780, 560)
        self.setMinimumSize(700, 480)
        config = conf.get()

        try:
            from . import qt_theme

            self.setStyleSheet(qt_theme.settings_dialog_qss())
        except Exception:
            pass

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- left nav (colored icon squares, System Settings style) ---
        nav = QWidget()
        nav.setObjectName("awdNav")
        nav.setFixedWidth(198)
        nav.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        nav_box = QVBoxLayout(nav)
        nav_box.setContentsMargins(10, 14, 10, 12)
        # 4px here + the 3px top/bottom margin in the button's QSS = a clear
        # 10px gutter between painted pills.
        nav_box.setSpacing(4)

        pages = [
            ("general", tr("page_general"), "#8E8E93"),
            ("look", tr("page_look"), "#007AFF"),
            ("decks", tr("page_decks"), "#34C759"),
            ("fsrs", "FSRS", "#AF52DE"),
            ("events", tr("page_events"), "#FF9500"),
            ("about", tr("page_about"), "#5856D6"),
        ]
        self._page_labels = [label for _, label, _ in pages]
        self._nav_buttons = []
        for index, (kind, label, color) in enumerate(pages):
            button = QPushButton(label)
            button.setObjectName("awdNavBtn")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            try:
                from . import qt_theme

                button.setIcon(QIcon(qt_theme.nav_icon(kind, color)))
                button.setIconSize(QSize(23, 23))
            except Exception:
                pass
            button.clicked.connect(lambda _checked, i=index: self._show_page(i))
            nav_box.addWidget(button)
            self._nav_buttons.append(button)
        nav_box.addStretch(1)
        root.addWidget(nav)

        # --- right column: title bar, page stack, footer buttons ---
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self._page_title = QLabel()
        self._page_title.setObjectName("awdPageTitle")
        self._page_title.setFixedHeight(46)
        right.addWidget(self._page_title)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_general_page(config))
        self._stack.addWidget(self._build_look_page(config))
        self._stack.addWidget(self._build_decks_page(config))
        self._stack.addWidget(self._build_fsrs_page())
        self._stack.addWidget(self._build_events_page(config))
        self._stack.addWidget(self._build_about_page())
        right.addWidget(self._stack, 1)

        foot = QWidget()
        foot.setObjectName("awdFootBar")
        foot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        foot_box = QHBoxLayout(foot)
        foot_box.setContentsMargins(16, 10, 16, 10)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        foot_box.addWidget(buttons)
        right.addWidget(foot)

        root.addLayout(right, 1)
        self._show_page(0)

    # --- building blocks (design: grouped inset cards with hairline rows) ---

    def _wrap_page(self, content: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(content)
        return area

    def _page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(20, 18, 20, 24)
        # Generous air between blocks, System Settings style; each block keeps
        # its own caption and hint tight against its card (see _block).
        box.setSpacing(30)
        return page, box

    def _row(self, title: str, control=None, subtitle: str = "") -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(12)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("awdRowTitle")
        text_box.addWidget(title_label)
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("awdRowSub")
            sub_label.setWordWrap(True)
            text_box.addWidget(sub_label)
        layout.addLayout(text_box, 1)
        if control is not None:
            layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _group(self, *rows: QWidget) -> QWidget:
        group = QWidget()
        group.setObjectName("awdGroup")
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(group)
        v.setContentsMargins(0, 1, 0, 1)
        v.setSpacing(0)
        for i, row in enumerate(rows):
            if i:
                sep = QFrame()
                sep.setObjectName("awdSep")
                sep.setFixedHeight(1)
                v.addWidget(sep)
            v.addWidget(row)
        return group

    def _block(self, box: QVBoxLayout, title: str, *rows: QWidget, hint: str = "") -> QWidget:
        """A section caption, its grouped card and an optional footnote —
        one unit, so the page's generous spacing lands *between* groups
        rather than between a caption and the card it belongs to."""
        block = QWidget()
        v = QVBoxLayout(block)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(7)
        if title:
            caption = QLabel(title.upper())
            caption.setObjectName("awdSection")
            v.addWidget(caption)
        group = self._group(*rows)
        v.addWidget(group)
        if hint:
            note = QLabel(hint)
            note.setObjectName("awdRowSub")
            note.setWordWrap(True)
            v.addWidget(note)
        box.addWidget(block)
        return group

    def _actions_row(self, *buttons: QPushButton) -> QWidget:
        """A card row holding right-aligned action buttons."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(8)
        layout.addStretch(1)
        for button in buttons:
            layout.addWidget(button)
        return row

    def _switch(self, checked: bool) -> QCheckBox:
        switch = QCheckBox()
        switch.setChecked(checked)
        return switch

    def _segmented(self, options, current: str):
        wrap = QWidget()
        wrap.setObjectName("awdSeg")
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        group = QButtonGroup(wrap)
        group.setExclusive(True)
        for key, label in options:
            button = QPushButton(label)
            button.setObjectName("awdSegBtn")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("awdKey", key)
            if key == current:
                button.setChecked(True)
            group.addButton(button)
            layout.addWidget(button)
        return wrap, group

    @staticmethod
    def _seg_value(group: QButtonGroup, fallback: str) -> str:
        button = group.checkedButton()
        value = button.property("awdKey") if button else None
        return value or fallback

    # --- pages ---

    def _build_general_page(self, config: dict) -> QScrollArea:
        page, box = self._page()

        self.name_edit = QLineEdit(config.get("userName", ""))
        self.name_edit.setPlaceholderText(mw.pm.name or "")
        self.name_edit.setFixedWidth(200)

        self.greeting_edit = QLineEdit(config.get("customGreeting", ""))
        self.greeting_edit.setFixedWidth(200)

        # Languages come from the i18n folder, so dropping in a new locale
        # file is all it takes to offer it here.
        self.lang_box = QComboBox()
        self.lang_box.addItem(tr("lang_auto"), "auto")
        for code, name in available_languages():
            self.lang_box.addItem(name, code)
        index = self.lang_box.findData(config.get("language", "auto"))
        self.lang_box.setCurrentIndex(max(0, index))

        self._block(
            box,
            "",
            self._row(tr("display_name"), self.name_edit),
            self._row(tr("custom_greeting"), self.greeting_edit, tr("custom_greeting_hint")),
            self._row(tr("language"), self.lang_box, tr("language_hint")),
        )

        sidebar_mode = config.get("sidebarMode", "hidden")
        if sidebar_mode not in SIDEBAR_ORDER:
            sidebar_mode = "hidden"
        sidebar_widget, self.sidebar_seg = self._segmented(
            [
                ("full", tr("sidebar_full")),
                ("compact", tr("sidebar_compact")),
                ("hidden", tr("sidebar_hidden")),
            ],
            sidebar_mode,
        )
        self.show_stats = self._switch(bool(config.get("showStats", True)))
        self.show_heatmap = self._switch(bool(config.get("showHeatmap", True)))
        self.show_pomodoro = self._switch(bool(config.get("showPomodoro", True)))
        self._block(
            box,
            tr("dashboard"),
            self._row(tr("sidebar"), sidebar_widget),
            self._row(tr("show_stats"), self.show_stats),
            self._row(tr("show_heatmap"), self.show_heatmap),
            self._row(tr("show_pomodoro"), self.show_pomodoro),
        )

        self.focus_minutes = QSpinBox()
        self.focus_minutes.setRange(5, 120)
        self.focus_minutes.setValue(int(config.get("pomodoroFocusMinutes", 25)))
        self.focus_minutes.setFixedWidth(90)
        self.break_minutes = QSpinBox()
        self.break_minutes.setRange(1, 60)
        self.break_minutes.setValue(int(config.get("pomodoroBreakMinutes", 5)))
        self.break_minutes.setFixedWidth(90)
        self._block(
            box,
            "Pomodoro",
            self._row(tr("focus_minutes"), self.focus_minutes),
            self._row(tr("break_minutes"), self.break_minutes),
        )

        box.addStretch(1)
        return self._wrap_page(page)

    def _build_look_page(self, config: dict) -> QScrollArea:
        page, box = self._page()

        from ..core.themes import ALIASES
        from .theme_editor import ThemePicker

        current_theme = ALIASES.get(config.get("theme", "glass"), config.get("theme"))
        self.theme_picker = ThemePicker(current_theme, config.get("customAccent"))
        picker_row = QWidget()
        picker_layout = QVBoxLayout(picker_row)
        picker_layout.setContentsMargins(14, 12, 14, 13)
        picker_layout.addWidget(self.theme_picker)
        self._block(box, tr("theme_section"), picker_row)

        rows = []

        # Light/dark mode — reads and writes Anki's own theme setting, so the
        # whole app (dialogs, editor, ...) switches together with the add-on.
        theme_map = _anki_theme_map()
        self.appearance_seg = None
        if theme_map:
            current_appearance = "system"
            try:
                reverse = {v: k for k, v in theme_map.items()}
                current_appearance = reverse.get(mw.pm.theme(), "system")
            except Exception:
                pass
            appearance_widget, self.appearance_seg = self._segmented(
                [
                    ("light", tr("appearance_light")),
                    ("dark", tr("appearance_dark")),
                    ("system", tr("appearance_system")),
                ],
                current_appearance,
            )
            rows.append(self._row(tr("appearance"), appearance_widget))

        if rows:
            self._block(box, "", *rows)

        self.style_overview = self._switch(bool(config.get("styleOverview", True)))
        self.style_reviewer = self._switch(bool(config.get("styleReviewer", True)))
        self.style_toolbar = self._switch(bool(config.get("styleToolbar", True)))
        self.style_system = self._switch(bool(config.get("styleSystemScreens", True)))
        self._block(
            box,
            tr("section_apply_theme"),
            self._row(tr("style_overview"), self.style_overview),
            self._row(tr("style_reviewer"), self.style_reviewer, tr("style_reviewer_hint")),
            self._row(tr("style_toolbar"), self.style_toolbar),
            self._row(tr("style_system"), self.style_system, tr("style_system_hint")),
        )

        self.hide_bottom = self._switch(bool(config.get("hideNativeBottomBar", True)))
        self.hide_toolbar = self._switch(bool(config.get("hideNativeToolbar", False)))
        self._block(
            box,
            tr("section_native"),
            self._row(tr("hide_bottom_bar"), self.hide_bottom, tr("native_hint")),
            self._row(tr("hide_toolbar"), self.hide_toolbar, tr("native_hint")),
        )

        box.addStretch(1)
        return self._wrap_page(page)

    def _build_fsrs_page(self) -> QScrollArea:
        """FSRS lives in Anki's scheduler; this page drives it from one place."""
        page, box = self._page()

        from ..features import fsrs

        self._fsrs_presets = fsrs.presets() if fsrs.available() else []
        self._fsrs_retention = {}
        self._fsrs_initial_retention = {}
        self._fsrs_enabled = None

        if not fsrs.available():
            unsupported = QLabel(tr("fsrs_unavailable"))
            unsupported.setObjectName("awdRowSub")
            unsupported.setWordWrap(True)
            box.addWidget(unsupported)
            box.addStretch(1)
            return self._wrap_page(page)

        self._fsrs_enabled = self._switch(fsrs.is_enabled())
        self._block(
            box,
            "",
            self._row(tr("fsrs_enable"), self._fsrs_enabled, tr("fsrs_enable_hint")),
            hint=tr("fsrs_enable_note"),
        )

        if not self._fsrs_presets:
            box.addStretch(1)
            return self._wrap_page(page)

        for conf in self._fsrs_presets:
            percent = round(fsrs.desired_retention(conf) * 100)
            self._fsrs_retention[int(conf["id"])] = percent
            self._fsrs_initial_retention[int(conf["id"])] = percent

        self.fsrs_preset_box = QComboBox()
        self.fsrs_preset_box.setMinimumWidth(240)
        for conf in self._fsrs_presets:
            self.fsrs_preset_box.addItem(str(conf["name"]), int(conf["id"]))
        self._fsrs_current_id = int(self._fsrs_presets[0]["id"])

        self.fsrs_retention = QSpinBox()
        self.fsrs_retention.setRange(70, 99)
        self.fsrs_retention.setSuffix("%")
        self.fsrs_retention.setFixedWidth(90)
        self.fsrs_retention.setValue(self._fsrs_retention[self._fsrs_current_id])

        self.fsrs_params_label = QLabel()
        self.fsrs_params_label.setObjectName("awdRowSub")

        self.fsrs_preset_box.currentIndexChanged.connect(self._fsrs_preset_changed)

        optimize_button = QPushButton(tr("fsrs_optimize"))
        optimize_button.setCursor(Qt.CursorShape.PointingHandCursor)
        optimize_button.clicked.connect(lambda: self._fsrs_run("optimize"))
        evaluate_button = QPushButton(tr("fsrs_evaluate"))
        evaluate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        evaluate_button.clicked.connect(lambda: self._fsrs_run("evaluate"))

        self._block(
            box,
            tr("fsrs_params_section"),
            self._row(tr("fsrs_preset"), self.fsrs_preset_box),
            self._row(tr("fsrs_retention"), self.fsrs_retention, tr("fsrs_retention_hint")),
            self._row(tr("fsrs_params"), self.fsrs_params_label),
            self._actions_row(optimize_button, evaluate_button),
            hint=tr("fsrs_params_hint"),
        )

        self._refresh_fsrs_params_label()
        box.addStretch(1)
        return self._wrap_page(page)

    def _refresh_fsrs_params_label(self) -> None:
        from ..features import fsrs

        conf = fsrs.preset(self._fsrs_current_id)
        count = len(fsrs.params(conf)) if conf else 0
        if not count:
            text = tr("fsrs_params_none")
        else:
            text = tr("fsrs_params_count", n=count)
            days = fsrs.days_since_optimize()
            if days is not None:
                text += " · " + (
                    tr("fsrs_optimized_today")
                    if days <= 0
                    else tr("fsrs_optimized_days", n=days)
                )
        self.fsrs_params_label.setText(text)

    def _fsrs_preset_changed(self, index: int) -> None:
        # Keep the edit made to the preset we're leaving, then show the new one.
        self._fsrs_retention[self._fsrs_current_id] = self.fsrs_retention.value()
        new_id = self.fsrs_preset_box.itemData(index)
        if new_id is None:
            return
        self._fsrs_current_id = int(new_id)
        self.fsrs_retention.setValue(self._fsrs_retention[self._fsrs_current_id])
        self._refresh_fsrs_params_label()

    def _fsrs_run(self, action: str) -> None:
        """Optimising/evaluating opens Anki's progress window, which can't sit
        above this modal dialog — so save and close first, like deck actions."""
        conf_id = self._fsrs_current_id
        self._save()
        from aqt.qt import QTimer

        from ..features import fsrs

        runner = fsrs.optimize if action == "optimize" else fsrs.evaluate
        QTimer.singleShot(0, lambda: runner(conf_id))

    def _save_fsrs(self) -> None:
        """Write desired retention for edited presets, then the global switch."""
        if self._fsrs_enabled is None:
            return
        from ..features import fsrs

        if getattr(self, "_fsrs_retention", None):
            self._fsrs_retention[self._fsrs_current_id] = self.fsrs_retention.value()
            for conf_id, percent in self._fsrs_retention.items():
                if percent == self._fsrs_initial_retention.get(conf_id):
                    continue
                conf = fsrs.preset(conf_id)
                if conf is None:
                    continue
                conf["desiredRetention"] = percent / 100
                fsrs.save_preset(conf)

        wanted = self._fsrs_enabled.isChecked()
        if wanted != fsrs.is_enabled():
            # Enabling recomputes memory states for the whole collection, so
            # show progress rather than freezing on a silent call.
            mw.progress.start(label=tr("fsrs_applying"), immediate=True)
            try:
                fsrs.set_enabled(wanted)
            finally:
                mw.progress.finish()

    def _build_events_page(self, config: dict) -> QScrollArea:
        page, box = self._page()

        self._events = [
            e
            for e in (config.get("events") or [])
            if isinstance(e, dict) and e.get("name") and e.get("date")
        ]

        caption = QLabel(tr("exam_countdown").upper())
        caption.setObjectName("awdSection")

        self.events_list = QListWidget()
        self.events_list.setObjectName("awdEventsList")

        footer = QWidget()
        footer.setObjectName("awdListFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(4, 2, 4, 2)
        footer_layout.setSpacing(2)
        add_button = QPushButton("+")
        add_button.setObjectName("awdMini")
        add_button.setToolTip(tr("add_event"))
        add_button.clicked.connect(self._add_event)
        minus_button = QPushButton("−")
        minus_button.setObjectName("awdMini")
        minus_button.setToolTip(tr("remove_event"))
        minus_button.clicked.connect(self._remove_event)
        footer_layout.addWidget(add_button)
        footer_layout.addWidget(minus_button)
        footer_layout.addStretch(1)

        block = QWidget()
        block_box = QVBoxLayout(block)
        block_box.setContentsMargins(0, 0, 0, 0)
        block_box.setSpacing(7)
        block_box.addWidget(caption)
        list_box = QVBoxLayout()
        list_box.setSpacing(0)
        list_box.addWidget(self.events_list)
        list_box.addWidget(footer)
        block_box.addLayout(list_box)
        hint = QLabel(tr("events_hint"))
        hint.setObjectName("awdRowSub")
        hint.setWordWrap(True)
        block_box.addWidget(hint)
        box.addWidget(block)

        self._refresh_events_list()
        box.addStretch(1)
        return self._wrap_page(page)

    def _build_decks_page(self, config: dict) -> QScrollArea:
        """Card skin per top-level deck; the choice covers all its subdecks."""
        page, box = self._page()

        from ..screens import card_skin

        self._skin_switches = {}
        # Effective (possibly inherited) value at open time, so _save only
        # touches decks the user actually flipped.
        self._skin_initial = {}
        # Subdeck ids, so flipping a parent can clear their stale overrides.
        self._skin_descendants = {}
        rows = []
        try:
            tree = mw.col.sched.deck_due_tree()
            nodes = list(tree.children)
        except Exception:
            nodes = []

        def descendants(node):
            ids = []
            for child in node.children:
                ids.append(int(child.deck_id))
                ids.extend(descendants(child))
            return ids

        for node in nodes:
            did = int(node.deck_id)
            enabled = card_skin.skin_enabled_for_deck(did)
            switch = self._switch(enabled)
            self._skin_switches[did] = switch
            self._skin_initial[did] = enabled
            self._skin_descendants[did] = descendants(node)
            subtitle = ""
            count = len(self._skin_descendants[did])
            if count:
                subtitle = tr("subdecks_included", n=count)
            rows.append(self._row(node.name, switch, subtitle))

        if rows:
            self._block(box, tr("card_skin_section"), *rows, hint=tr("card_skin_hint"))
        else:
            empty = QLabel(tr("empty_title"))
            empty.setObjectName("awdRowSub")
            box.addWidget(empty)

        # A policy rather than a deck, so it sits in its own card below the list.
        self.card_skin_default = self._switch(
            bool(config.get("cardSkinDefault", True))
        )
        self._block(
            box,
            "",
            self._row(tr("card_skin_default"), self.card_skin_default),
            hint=tr("card_skin_default_hint"),
        )

        # --- deck management (moved off the dashboard's ⋮ menu) ---
        self.deck_combo = QComboBox()
        self.deck_combo.setMinimumWidth(240)
        try:
            for deck in sorted(
                mw.col.decks.all_names_and_ids(), key=lambda d: d.name.lower()
            ):
                depth = deck.name.count("::")
                leaf = deck.name.rsplit("::", 1)[-1]
                self.deck_combo.addItem("    " * depth + leaf, int(deck.id))
        except Exception:
            pass

        buttons = []
        for key, label, danger in (
            ("rename", tr("deck_rename"), False),
            ("options", tr("deck_options"), False),
            ("export", tr("deck_export"), False),
            ("delete", tr("deck_delete"), True),
        ):
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if danger:
                button.setObjectName("awdDanger")
            button.clicked.connect(lambda _c, k=key: self._deck_action(k))
            buttons.append(button)

        self._block(
            box,
            tr("deck_manage_section"),
            self._row(tr("deck_pick"), self.deck_combo),
            self._actions_row(*buttons),
            hint=tr("deck_manage_hint"),
        )

        box.addStretch(1)
        return self._wrap_page(page)

    def _deck_action(self, kind: str) -> None:
        """Run one of Anki's own deck commands on the selected deck.

        This dialog is modal, so it saves and closes first — each command opens its own
        window that would otherwise be stuck behind it.
        """
        did = self.deck_combo.currentData()
        if did is None:
            return
        self._save()
        from aqt.qt import QTimer

        QTimer.singleShot(0, lambda: _run_deck_action(kind, int(did)))

    # --- behaviour ---

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._page_title.setText(self._page_labels[index])
        for i, button in enumerate(self._nav_buttons):
            button.setChecked(i == index)

    def _refresh_events_list(self) -> None:
        self.events_list.clear()
        for event in self._events:
            shown = QDate.fromString(event["date"], "yyyy-MM-dd").toString(
                date_input_format()
            ) or event["date"]
            self.events_list.addItem(f'{event["name"]} — {shown}')
        # Empty = a slim strip; the list grows with each event, then scrolls.
        rows = min(max(len(self._events), 1), 8)
        self.events_list.setFixedHeight(10 + rows * 27)

    def _add_event(self) -> None:
        dialog = _EventDialog(self)
        if dialog.exec():
            self._events.append(dialog.result_event())
            self._events.sort(key=lambda e: e.get("date", ""))
            self._refresh_events_list()

    def _remove_event(self) -> None:
        row = self.events_list.currentRow()
        if 0 <= row < len(self._events):
            del self._events[row]
            self._refresh_events_list()

    # Everything except the palette changes what the page is made of, so a
    # re-render is unavoidable; a palette-only change can just cross-fade.
    # --- about + reset -------------------------------------------------------

    def _build_about_page(self) -> QScrollArea:
        page, box = self._page()

        def value_row(label: str, value: str) -> QWidget:
            text = QLabel(value)
            text.setObjectName("awdRowSub")
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            text.setOpenExternalLinks(True)
            return self._row(label, text)

        meta = _addon_meta()
        self._block(
            box,
            "Awesome Dashboard",
            value_row(tr("about_version"), meta["version"]),
            value_row(tr("about_package"), meta["package"]),
            value_row(tr("about_anki"), meta["anki"]),
            value_row(tr("about_licence"), "MIT"),
        )
        self._block(
            box,
            tr("about_source"),
            value_row("GitHub", f'<a href="{HOMEPAGE}">{HOMEPAGE}</a>'),
            value_row(tr("about_ankiweb"), f'<a href="{ANKIWEB_PAGE}">{ANKIWEB_CODE}</a>'),
        )

        settings_button = QPushButton(tr("reset"))
        settings_button.clicked.connect(lambda: self._reset_settings())
        progress_button = QPushButton(tr("reset"))
        progress_button.setObjectName("awdDanger")
        progress_button.clicked.connect(lambda: self._reset_progress())
        all_button = QPushButton(tr("reset"))
        all_button.setObjectName("awdDanger")
        all_button.clicked.connect(lambda: self._reset_all())
        self._block(
            box,
            tr("reset_section"),
            self._row(tr("reset_settings"), settings_button, tr("reset_settings_hint")),
            self._row(tr("reset_progress"), progress_button, tr("reset_progress_hint")),
            self._row(tr("reset_all"), all_button, tr("reset_all_hint")),
        )

        box.addStretch(1)
        return self._wrap_page(page)

    def _reset_settings(self, *, ask: bool = True) -> bool:
        from aqt.utils import askUser, tooltip

        if ask and not askUser(
            tr("reset_settings_confirm"), parent=self, title="Awesome Dashboard"
        ):
            return False
        conf.save(dict(conf.DEFAULTS))
        try:
            # The Pomodoro tally is add-on state too, but it lives in the
            # collection rather than the add-on config, so it needs clearing
            # by hand.
            from ..features.pomodoro import SESSIONS_KEY

            mw.col.set_config(SESSIONS_KEY, None)
        except Exception:
            pass
        try:
            from . import qt_theme

            qt_theme.apply_app_palette()
            qt_theme.animate_theme_change()
        except Exception:
            pass
        _reload_current_screen()
        if ask:
            tooltip(tr("reset_done"), parent=mw)
        # The open dialog still holds the pre-reset values, so saving on the way
        # out would write them straight back.
        self.reject()
        return True

    def _reset_progress(
        self, card_ids=None, *, ask: bool = True, everything: bool = False
    ) -> bool:
        """Send cards back to new and drop the review history behind them.

        Rescheduling alone is not "as if freshly added": the revlog rows stay,
        so the streak, heatmap and retention all still show the work. Those
        rows go too, which is why this also forces a full sync.
        """
        deck_count = 0
        if card_ids is None:
            picked = _DeckResetDialog(self).picked()
            if not picked:
                return False
            deck_count = len(picked)
            card_ids = []
            for did in picked:
                try:
                    card_ids.extend(mw.col.decks.cids(did, children=True))
                except Exception:
                    pass
        if not card_ids:
            return False

        if ask:
            from aqt.utils import askUser

            if not askUser(
                tr("reset_pick_confirm", n=len(card_ids), decks=deck_count),
                parent=self,
                title="Awesome Dashboard",
            ):
                return False

        from aqt.operations import CollectionOp
        from aqt.utils import tooltip

        ids = list(card_ids)

        def op(col):
            # restore_position + reset_counts is exactly "as if freshly added":
            # back to the original new-card slot with reps and lapses cleared.
            changes = col.sched.schedule_cards_as_new(
                ids, restore_position=True, reset_counts=True
            )
            # Rewriting history cannot be merged by a normal sync, and the raw
            # delete is outside the undo entry above — so flag the full sync.
            col.mod_schema(check=False)
            if everything:
                col.db.execute("delete from revlog")
            else:
                for start in range(0, len(ids), 500):
                    chunk = ",".join(str(int(cid)) for cid in ids[start:start + 500])
                    col.db.execute(f"delete from revlog where cid in ({chunk})")
            return changes

        def done(_out) -> None:
            from ..core import heatmap_scale, stats

            # The stored scale describes a review log that no longer exists.
            heatmap_scale.clear()
            stats.invalidate_cache()
            _reload_current_screen()
            tooltip(tr("reset_done"), parent=mw)

        CollectionOp(parent=mw, op=op).success(done).run_in_background()
        return True

    def _reset_all(self) -> None:
        """Factory reset — every card, every review, every setting."""
        try:
            # Straight from the table rather than a search string, so "every
            # card" cannot be narrowed by how a search happens to be parsed.
            card_ids = mw.col.db.list("select id from cards")
        except Exception:
            card_ids = []

        from aqt.utils import askUser

        # One prompt, spelling out each consequence — this is the only action
        # here that undo cannot walk back.
        if not askUser(
            tr("reset_all_confirm", n=len(card_ids)),
            parent=self,
            title="Awesome Dashboard",
            defaultno=True,
        ):
            return
        self._reset_progress(card_ids, ask=False, everything=True)
        self._reset_settings(ask=False)

    LAYOUT_KEYS = (
        "userName",
        "customGreeting",
        "language",
        "sidebarMode",
        "showStats",
        "showHeatmap",
        "showPomodoro",
        "hideNativeBottomBar",
        "hideNativeToolbar",
        "styleOverview",
        "styleReviewer",
        "styleToolbar",
        "styleSystemScreens",
        "events",
    )

    def _save(self) -> None:
        config = conf.get()
        before = {key: config.get(key) for key in self.LAYOUT_KEYS}
        skin_map = dict(config.get("cardSkinDecks") or {})
        for did, switch in getattr(self, "_skin_switches", {}).items():
            if switch.isChecked() == self._skin_initial.get(did):
                continue
            skin_map[str(did)] = switch.isChecked()
            # A subdeck's own entry would win over the parent's, so drop them
            # and let the whole subtree follow this switch.
            for child_id in self._skin_descendants.get(did, []):
                skin_map.pop(str(child_id), None)
        config.update(
            {
                "userName": self.name_edit.text().strip(),
                "customGreeting": self.greeting_edit.text().strip(),
                "theme": self.theme_picker.theme(),
                "customAccent": self.theme_picker.accent(),
                "language": self.lang_box.currentData(),
                "sidebarMode": self._seg_value(self.sidebar_seg, "hidden"),
                "showStats": self.show_stats.isChecked(),
                "showHeatmap": self.show_heatmap.isChecked(),
                "showPomodoro": self.show_pomodoro.isChecked(),
                "pomodoroFocusMinutes": self.focus_minutes.value(),
                "pomodoroBreakMinutes": self.break_minutes.value(),
                "hideNativeBottomBar": self.hide_bottom.isChecked(),
                "hideNativeToolbar": self.hide_toolbar.isChecked(),
                "styleOverview": self.style_overview.isChecked(),
                "styleReviewer": self.style_reviewer.isChecked(),
                "styleToolbar": self.style_toolbar.isChecked(),
                "styleSystemScreens": self.style_system.isChecked(),
                "events": self._events,
                "cardSkinDecks": skin_map,
                "cardSkinDefault": self.card_skin_default.isChecked(),
            }
        )
        conf.save(config)
        layout_changed = any(config.get(key) != before[key] for key in self.LAYOUT_KEYS)

        try:
            self._save_fsrs()
        except Exception as e:
            print(f"[Awesome Dashboard] FSRS settings save failed: {e}")

        if self.appearance_seg is not None:
            theme_map = _anki_theme_map()
            if theme_map:
                try:
                    new_theme = theme_map[self._seg_value(self.appearance_seg, "system")]
                    if mw.pm.theme() != new_theme:
                        mw.set_theme(new_theme)
                except Exception:
                    pass

        self.accept()
        try:
            from ..screens import dashboard
            from . import qt_theme

            qt_theme.apply_app_palette()
            dashboard.apply_bar_visibility(mw.state)
            language = config.get("language", "auto")
            if language != "auto" and language != before["language"]:
                from aqt.qt import QTimer

                # This dialog is modal; let it close before asking.
                QTimer.singleShot(
                    0,
                    lambda code=language, was=before["language"]:
                    _offer_anki_language(code, was),
                )
            if layout_changed:
                if mw.state == "deckBrowser":
                    mw.deckBrowser.refresh()
                elif mw.state == "overview":
                    mw.overview.refresh()
            else:
                qt_theme.animate_theme_change()
            mw.toolbar.draw()
        except Exception:
            pass
