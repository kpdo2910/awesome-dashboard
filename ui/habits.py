"""Habits — the Qt side of the habit tracker.

Two pieces: `HabitListPanel` (add / edit / reorder / archive / delete), which is
the Habits page of the settings dialog, and `HabitEditor`, the dialog for one
habit — reached from that page, and straight from the dashboard's + button.

Nothing here has a Cancel. `HabitStore` writes are debounced, not transactional,
and the dashboard behind the dialog is ticking the same records — offering to
"discard" changes that a habit tick may already have interleaved with would be
a lie. Each edit lands when its own dialog is accepted, so a habit change does
**not** ride on the settings dialog's Save button; the panel's hint says so.
"""

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSize,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..core import themes
from ..core.translations import tr, weekday_short
from .qtutil import AwdLineEdit

# Put away / take back out. Text glyphs, not emoji, so the footer is one
# monochrome row with +/−/✎ — and so nothing here can be clipped the way a
# colour emoji is. Doubled arrows, to stay distinct from the ↑↓ that reorder.
ARCHIVE_GLYPH = "⇩"
UNARCHIVE_GLYPH = "⇧"
from ..features.habits import models
from ..features.habits.store import get_store


def _qss() -> str:
    from . import qt_theme

    try:
        return qt_theme.habit_dialog_qss()
    except Exception:
        return ""


def schedule_text(habit) -> str:
    """One line describing when a habit is due, for lists and tooltips."""
    kind = habit.schedule_kind
    if kind == models.SCHEDULE_WEEKDAYS:
        days = habit.schedule.get("days", [])
        if len(days) == 7:
            return tr("sched_daily")
        return ", ".join(weekday_short(day - 1) for day in days)
    if kind == models.SCHEDULE_TIMES_PER_WEEK:
        return tr("sched_times_week_n", n=habit.schedule.get("n", 3))
    return tr("sched_daily")


def target_text(habit) -> str:
    """"30 min" for a count habit, empty for a yes/no one."""
    if not habit.is_count:
        return ""
    unit = habit.unit.strip()
    return f"{habit.target} {unit}".strip()


# --- small controls -----------------------------------------------------------

class _IconDialog(QDialog):
    """Emoji grid plus a free-text box — the grid is a shortcut, not a limit."""

    def __init__(self, parent, current: str):
        super().__init__(parent)
        self.setWindowTitle(tr("habit_icon"))
        self.setStyleSheet(_qss())
        self._chosen = current

        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(10)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for index, glyph in enumerate(models.ICONS):
            button = QPushButton(glyph)
            # Sized by qt_theme.habit_dialog_qss() alone — a setFixedSize here
            # loses to the stylesheet's max-height and the glyphs then overlap.
            button.setObjectName("awdIconCell")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _c=False, g=glyph: self._pick(g))
            grid.addWidget(button, index // 8, index % 8)
        box.addWidget(grid_host)

        row = QHBoxLayout()
        label = QLabel(tr("habit_icon_custom"))
        label.setObjectName("awdRowSub")
        self.edit = AwdLineEdit(current)
        self.edit.setMaxLength(4)
        self.edit.setFixedWidth(70)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.edit)
        box.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # Qt's own translations decide these labels otherwise, and Anki ships no
        # Qt catalogue for every language we do — the dialog then reads half in
        # the user's language and half in English.
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("done"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def _pick(self, glyph: str) -> None:
        self.edit.setText(glyph)
        self.accept()

    def icon(self) -> str:
        return self.edit.value().strip() or self._chosen or models.DEFAULT_ICON


class _ColorRow(QWidget):
    """Ten presets plus a free colour picker; the chosen one keeps a ring.

    The presets are a shortcut, not the range. A habit's colour is whatever hex
    is stored, so the last swatch opens `QColorDialog` and shows the result —
    without it, a colour that suits the user's theme but is not one of the ten
    was silently snapped back to the first preset on the next edit.
    """

    def __init__(self, current: str):
        super().__init__()
        self._value = current or models.DEFAULT_COLOR
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._buttons = {}
        for color in models.PALETTE:
            layout.addWidget(self._swatch(color))
        # The custom swatch carries whatever is not in the presets, so a stored
        # colour always has somewhere to show and something to click.
        self._custom = self._swatch(self._value if self._value not in models.PALETTE
                                    else "", custom=True)
        layout.addWidget(self._custom)
        self.set_value(self._value)

    def _swatch(self, color: str, custom: bool = False) -> QPushButton:
        button = QPushButton("…" if custom else "")
        button.setCheckable(True)
        button.setFixedSize(QSize(22, 22))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tr("habit_color_custom") if custom else color)
        if custom:
            button.clicked.connect(lambda _c=False: self._pick())
        else:
            button.clicked.connect(lambda _c=False, value=color: self.set_value(value))
            self._buttons[color] = button
        return button

    def _pick(self) -> None:
        from aqt.qt import QColor, QColorDialog

        chosen = QColorDialog.getColor(QColor(self._value), self, tr("pick_color"))
        if chosen.isValid():
            self.set_value(chosen.name())

    def set_value(self, color: str) -> None:
        self._value = color
        preset = color in models.PALETTE
        for key, button in self._buttons.items():
            self._paint(button, key, key == color)
        # Empty until something off-palette is chosen, so the row does not show
        # eleven colours when only ten are on offer.
        self._paint(self._custom, color if not preset else "", not preset)

    @staticmethod
    def _paint(button: QPushButton, color: str, chosen: bool) -> None:
        # The ring has to be part of the same stylesheet as the fill: a plain
        # QPushButton background would otherwise be repainted by the
        # dialog-wide QPushButton rule.
        ring = ("3px solid rgba(127,127,127,0.55)" if chosen
                else "1px solid rgba(127,127,127,0.25)")
        fill = color or "transparent"
        button.setChecked(chosen)
        button.setStyleSheet(
            f"QPushButton {{ background: {fill}; border: {ring};"
            f" border-radius: 11px; padding: 0; min-width: 0;"
            f" font-size: 11px; color: {'#fff' if color else 'palette(text)'}; }}"
        )

    def value(self) -> str:
        return self._value


class _WeekdayRow(QWidget):
    """Seven toggles, Monday first, matching the ISO days the schedule stores."""

    def __init__(self, days):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._buttons = {}
        for iso in range(1, 8):
            button = QPushButton(weekday_short(iso - 1))
            button.setObjectName("awdSegBtn")
            button.setCheckable(True)
            button.setChecked(iso in days)
            button.setFixedWidth(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._buttons[iso] = button
            layout.addWidget(button)

    def days(self) -> list:
        return [iso for iso, button in self._buttons.items() if button.isChecked()]


# --- the editor ------------------------------------------------------------------

class HabitEditor(QDialog):
    """Add or edit one habit. Returns the edited object through `habit()`."""

    def __init__(self, parent, habit=None):
        super().__init__(parent)
        self._original = habit
        self.setWindowTitle(tr("habit_edit") if habit else tr("habit_new"))
        self.setStyleSheet(_qss())
        self.setMinimumWidth(420)

        source = habit or models.Habit(name="", icon=models.DEFAULT_ICON,
                                       color=models.PALETTE[3])
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 18, 14)
        box.setSpacing(12)

        # --- name + icon ---
        head = QHBoxLayout()
        head.setSpacing(8)
        self._icon = source.icon
        self.icon_button = QPushButton(self._icon)
        # Sized by the stylesheet; the generic QPushButton padding would
        # otherwise take 36 of a fixed 40px and clip the emoji to a sliver.
        self.icon_button.setObjectName("awdIconBtn")
        self.icon_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_button.setToolTip(tr("habit_icon"))
        self.icon_button.clicked.connect(self._pick_icon)
        self.name_edit = AwdLineEdit(source.name)
        self.name_edit.setPlaceholderText(tr("habit_name_hint"))
        head.addWidget(self.icon_button)
        head.addWidget(self.name_edit, 1)
        box.addLayout(head)

        # Shown only once Save has been refused. A Save button that silently
        # does nothing reads as a broken control, and "the habit has no name
        # yet" is invisible from the outside.
        self.name_error = QLabel(tr("name_required"))
        self.name_error.setObjectName("awdFieldError")
        self.name_error.setVisible(False)
        box.addWidget(self.name_error)
        self.name_edit.valueEdited.connect(
            lambda: self.name_error.setVisible(False)
        )

        self.color_row = _ColorRow(source.color)
        box.addWidget(self._labelled(tr("habit_color"), self.color_row))

        # --- kind ---
        self.kind_seg, self.kind_group = self._segmented(
            [(models.KIND_BINARY, tr("habit_kind_binary")),
             (models.KIND_COUNT, tr("habit_kind_count"))],
            source.kind,
        )
        box.addWidget(self._labelled(tr("habit_kind"), self.kind_seg))

        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, models.MAX_TARGET)
        self.target_spin.setValue(source.target)
        self.target_spin.setFixedWidth(100)
        self.unit_edit = AwdLineEdit(source.unit)
        self.unit_edit.setPlaceholderText(tr("habit_unit_hint"))
        self.unit_edit.setFixedWidth(110)
        target_host = QWidget()
        target_layout = QHBoxLayout(target_host)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(6)
        target_layout.addWidget(self.target_spin)
        target_layout.addWidget(self.unit_edit)
        self.target_row = self._labelled(tr("habit_target"), target_host)
        box.addWidget(self.target_row)

        # --- schedule ---
        box.addWidget(self._separator())
        self.sched_seg, self.sched_group = self._segmented(
            [(models.SCHEDULE_DAILY, tr("sched_daily")),
             (models.SCHEDULE_WEEKDAYS, tr("sched_weekdays")),
             (models.SCHEDULE_TIMES_PER_WEEK, tr("sched_times_week"))],
            source.schedule_kind,
        )
        box.addWidget(self._labelled(tr("habit_schedule"), self.sched_seg))

        self.weekday_row = _WeekdayRow(source.schedule.get("days", [1, 2, 3, 4, 5]))
        box.addWidget(self.weekday_row)

        self.times_spin = QSpinBox()
        self.times_spin.setRange(1, 7)
        self.times_spin.setValue(int(source.schedule.get("n", 3)))
        self.times_spin.setFixedWidth(70)
        self.times_row = self._labelled(tr("habit_times_per_week"), self.times_spin)
        box.addWidget(self.times_row)

        hint = QLabel(tr("sched_times_week_hint"))
        hint.setObjectName("awdRowSub")
        hint.setWordWrap(True)
        self.times_hint = hint
        box.addWidget(hint)

        box.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

        for button in self.kind_group:
            button.clicked.connect(self._sync_rows)
        for button in self.sched_group:
            button.clicked.connect(self._sync_rows)
        self._sync_rows()
        self.name_edit.setFocus()

    # --- layout helpers (matched to the settings dialog) ---

    def _labelled(self, title: str, control: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("awdRowTitle")
        label.setMinimumWidth(96)
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("awdSep")
        line.setFixedHeight(1)
        return line

    def _segmented(self, options, current: str):
        wrap = QWidget()
        wrap.setObjectName("awdSeg")
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        buttons = []
        for key, label in options:
            button = QPushButton(label)
            button.setObjectName("awdSegBtn")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("awdKey", key)
            button.setChecked(key == current)
            layout.addWidget(button)
            buttons.append(button)
        if not any(b.isChecked() for b in buttons):
            buttons[0].setChecked(True)
        return wrap, buttons

    @staticmethod
    def _seg_value(buttons, fallback: str) -> str:
        for button in buttons:
            if button.isChecked():
                return button.property("awdKey")
        return fallback

    def _sync_rows(self) -> None:
        is_count = self._seg_value(self.kind_group, models.KIND_BINARY) == models.KIND_COUNT
        self.target_row.setVisible(is_count)
        kind = self._seg_value(self.sched_group, models.SCHEDULE_DAILY)
        self.weekday_row.setVisible(kind == models.SCHEDULE_WEEKDAYS)
        weekly = kind == models.SCHEDULE_TIMES_PER_WEEK
        self.times_row.setVisible(weekly)
        self.times_hint.setVisible(weekly)
        # Hidden rows still hold their space until the dialog is re-fitted.
        self.adjustSize()

    def _pick_icon(self) -> None:
        dialog = _IconDialog(self, self._icon)
        if dialog.exec():
            self._icon = dialog.icon()
            self.icon_button.setText(self._icon)

    def _accept(self) -> None:
        # `value()`, not `text()`: with an IME still composing, `text()` is empty
        # and Save refused a name the user could see in the field. See AwdLineEdit.
        if not self.name_edit.value().strip():
            self.name_error.setVisible(True)
            self.name_edit.setFocus()
            self.adjustSize()
            return
        self.accept()

    def habit(self):
        kind = self._seg_value(self.kind_group, models.KIND_BINARY)
        sched_kind = self._seg_value(self.sched_group, models.SCHEDULE_DAILY)
        if sched_kind == models.SCHEDULE_WEEKDAYS:
            schedule = {"kind": sched_kind, "days": self.weekday_row.days()}
        elif sched_kind == models.SCHEDULE_TIMES_PER_WEEK:
            schedule = {"kind": sched_kind, "n": self.times_spin.value()}
        else:
            schedule = {"kind": models.SCHEDULE_DAILY}
        base = self._original.to_dict() if self._original else {}
        base.update(
            {
                "name": self.name_edit.value().strip(),
                "icon": self._icon,
                "color": self.color_row.value(),
                "kind": kind,
                "target": self.target_spin.value(),
                "unit": self.unit_edit.value().strip(),
                "schedule": schedule,
            }
        )
        base.setdefault("id", models.new_id())
        return models.Habit.from_dict(base)


# --- the list panel -----------------------------------------------------------------

class HabitListPanel(QWidget):
    """The habit list and its footer, as one widget.

    A page of the settings dialog rather than a dialog of its own: habits are
    configuration, and a second modal window opened from the dashboard was one
    more place to look for them. `changed()` tells the host whether the
    dashboard needs repainting on the way out.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("awdHabits")

        self.store = get_store()
        self._changed = False
        self._measured = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        caption = QLabel(tr("habits").upper())
        caption.setObjectName("awdSection")
        root.addWidget(caption)

        self.list = QListWidget()
        self.list.setObjectName("awdEventsList")
        self.list.itemDoubleClicked.connect(lambda _item: self._edit())
        # The archive button flips between archive and restore, so it has to
        # follow the selection and not just the last rebuild.
        self.list.currentRowChanged.connect(lambda _row: self._sync_buttons())
        root.addWidget(self.list, 1)

        footer = QWidget()
        footer.setObjectName("awdListFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(4, 2, 4, 2)
        footer_layout.setSpacing(2)
        # +/− together, the same idiom as the events list in Settings. Both are
        # plain text glyphs, so they line up and neither can be clipped.
        for glyph, tip, slot in (
            ("+", tr("habit_add"), self._add),
            ("−", tr("habit_delete"), self._delete),
            ("✎", tr("habit_edit"), self._edit),
            ("↑", tr("habit_move_up"), lambda: self._move(-1)),
            ("↓", tr("habit_move_down"), lambda: self._move(1)),
        ):
            button = QPushButton(glyph)
            button.setObjectName("awdMiniEmoji")
            button.setToolTip(tip)
            button.clicked.connect(slot)
            footer_layout.addWidget(button)
        footer_layout.addStretch(1)
        self.archive_button = QPushButton(ARCHIVE_GLYPH)
        self.archive_button.setObjectName("awdMiniEmoji")
        self.archive_button.setToolTip(tr("habit_archive"))
        self.archive_button.clicked.connect(self._archive)
        footer_layout.addWidget(self.archive_button)
        root.addWidget(footer)

        self.show_archived = QCheckBox(tr("habit_show_archived"))
        self.show_archived.setChecked(
            not self.store.prefs().get("hideArchived", True)
        )
        self.show_archived.toggled.connect(self._toggle_archived)
        root.addWidget(self.show_archived)

        # No Report button. It opened a webview dialog on top of this page, on
        # top of Settings, and that stack is what hung the app. The report is
        # reached from the dashboard, where nothing else is modal.
        hint = QLabel(tr("habits_hint"))
        hint.setObjectName("awdRowSub")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._refresh()

    def changed(self) -> bool:
        """True once something here would change what the dashboard draws."""
        return self._changed

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Measure the rows once more here. A row's height depends on the font
        # the stylesheet gives it, and this panel only inherits the settings
        # dialog's sheet once it is inside the dialog — the height taken in
        # __init__ was taken with Qt's default font.
        if not self._measured:
            self._measured = True
            self._refresh()

    # --- list ---

    def _visible_habits(self) -> list:
        return self.store.habits(include_archived=self.show_archived.isChecked())

    def _row_widget(self, habit) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        glyph = QLabel(habit.icon)
        glyph.setFixedWidth(26)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # The habit's colour as a chip behind its icon, so the list reads the
        # same way as the dashboard strip.
        glyph.setStyleSheet(
            f"background: {themes.rgba(habit.color, 0.18)}; border-radius: 8px;"
            f" padding: 3px 0; font-size: 15px;"
        )
        layout.addWidget(glyph)

        text = QVBoxLayout()
        text.setSpacing(0)
        title = QLabel(habit.name)
        title.setObjectName("awdRowTitle")
        parts = [schedule_text(habit)]
        if habit.is_count:
            parts.append(target_text(habit))
        if habit.archived:
            parts.append(tr("habit_archived_tag"))
        subtitle = QLabel(" · ".join(p for p in parts if p))
        subtitle.setObjectName("awdRowSub")
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text, 1)
        # No streak here. This screen is for editing the definitions; the streak
        # belongs where the habit is actually ticked, and computing one per row
        # meant reading two years of log to draw a list.
        return row

    def _refresh(self) -> None:
        selected = self.list.currentRow()
        self.list.clear()
        habits = self._visible_habits()
        for habit in habits:
            item = QListWidgetItem()
            widget = self._row_widget(habit)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, habit.id)
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
        if habits:
            self.list.setCurrentRow(max(0, min(selected, len(habits) - 1)))
        self._fit_height()
        self._sync_buttons()

    def _fit_height(self) -> None:
        """Grow with the list, then scroll — the same idiom as the events list.

        The page around this is a QScrollArea, which honours a widget's size
        hint: left to itself a QListWidget asks for a fixed 256px, so a single
        habit sat in a tall empty box and eleven of them scrolled inside a
        scrolling page.
        """
        row = max(
            (self.list.item(i).sizeHint().height() for i in range(self.list.count())),
            default=0,
        )
        shown = min(max(self.list.count(), 1), 6)
        self.list.setFixedHeight(10 + shown * (row or 40))

    def _sync_buttons(self) -> None:
        habit = self._selected()
        archived = bool(habit and habit.archived)
        self.archive_button.setText(UNARCHIVE_GLYPH if archived else ARCHIVE_GLYPH)
        self.archive_button.setToolTip(
            tr("habit_unarchive") if archived else tr("habit_archive")
        )

    def _selected(self):
        item = self.list.currentItem()
        if item is None:
            return None
        return self.store.get(item.data(Qt.ItemDataRole.UserRole))

    # --- actions ---

    def _add(self) -> None:
        if not add_habit(self):
            return
        self._changed = True
        self._refresh()

    def _edit(self) -> None:
        habit = self._selected()
        if habit is None:
            return
        dialog = HabitEditor(self, habit)
        if not dialog.exec():
            return
        edited = dialog.habit()
        if edited is None:
            return
        self.store.replace(edited)
        self._changed = True
        self._refresh()

    def _move(self, delta: int) -> None:
        habit = self._selected()
        if habit is None:
            return
        # Reorder against the full list, archived included: moving a habit while
        # archived ones are hidden must not silently reshuffle them.
        ids = [h.id for h in self.store.habits(include_archived=True)]
        index = ids.index(habit.id)
        target = index + delta
        if not 0 <= target < len(ids):
            return
        ids[index], ids[target] = ids[target], ids[index]
        self.store.reorder(ids)
        self._changed = True
        self._refresh()
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.ItemDataRole.UserRole) == habit.id:
                self.list.setCurrentRow(row)
                break

    def _archive(self) -> None:
        habit = self._selected()
        if habit is None:
            return
        if habit.archived:
            self.store.unarchive(habit.id)
        else:
            self.store.archive(habit.id)
        self._changed = True
        self._refresh()

    def _delete(self) -> None:
        habit = self._selected()
        if habit is None:
            return
        answer = QMessageBox.warning(
            self,
            tr("habit_delete"),
            tr("habit_delete_confirm", name=habit.name),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.store.purge(habit.id)
        self._changed = True
        self._refresh()

    def _toggle_archived(self, shown: bool) -> None:
        self.store.set_pref("hideArchived", not shown)
        self._refresh()


# --- entry points -------------------------------------------------------------------

def add_habit(parent=None) -> bool:
    """The editor on its own — the dashboard's + button, and the panel's.

    Returns True when a habit was actually stored, so the caller can decide
    whether the screen behind it has to be redrawn. Flushes rather than leaving
    it to the debounce: this is the end of a deliberate edit, not one tap in a
    burst of them, and the dashboard is about to re-render from the store.
    """
    dialog = HabitEditor(parent or mw)
    if not dialog.exec():
        return False
    habit = dialog.habit()
    if habit is None:
        return False
    store = get_store()
    store.add(habit)
    store.flush()
    return True
