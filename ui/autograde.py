"""Per-deck auto-grading thresholds.

Switching "use the deck's own timing" off deletes the numbers rather than
storing a copy, so a deck that follows its parent keeps following it.
"""

from aqt.qt import (
    QDialog,
    QDialogButtonBox,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..core.translations import tr
from ..features.autograde import rules

FIELDS = ("easyMax", "goodMax", "hardMax")


class AwdDeckGradeDialog(QDialog):


    def __init__(self, parent, deck_name: str, entry: dict, inherited: dict):
        super().__init__(parent)
        self.setObjectName("awdSettings")
        self.setWindowTitle(deck_name)
        self.setMinimumWidth(420)
        try:
            from . import qt_theme

            self.setStyleSheet(qt_theme.settings_dialog_qss())
        except Exception:
            pass

        self._inherited = rules.normalise(dict(inherited))
        box = QVBoxLayout(self)
        box.setContentsMargins(20, 18, 20, 16)
        box.setSpacing(16)

        rows = parent  # the settings dialog owns the row/block helpers
        self._own = rows._switch(any(key in entry for key in FIELDS))
        self._own.toggled.connect(self._sync_enabled)

        self.spins = {}
        controls = [rows._row(tr("ag_deck_own"), self._own,
                              tr("ag_deck_own_hint"))]
        start = rules.normalise({**self._inherited, **entry})
        # Literal tr() calls, so tools/check_locales.py can see them used.
        labels = {
            "easyMax": tr("ag_easy_max"),
            "goodMax": tr("ag_good_max"),
            "hardMax": tr("ag_hard_max"),
        }
        for key in FIELDS:
            spin = QSpinBox()
            spin.setRange(1, 600)
            spin.setSuffix(" s")
            spin.setValue(int(start[key]))
            spin.setFixedWidth(96)
            spin.valueChanged.connect(self._sync_order)
            self.spins[key] = spin
            controls.append(rows._row(labels[key], spin))
        box.addWidget(rows._group(*controls))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # Qt's own catalogue is not shipped for every language the add-on has,
        # so a standard button would leave the dialog half translated.
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("done"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

        self._sync_enabled()
        self._sync_order()

    def _sync_enabled(self) -> None:
        own = self._own.isChecked()
        for key, spin in self.spins.items():
            spin.setEnabled(own)
            if not own:
                spin.blockSignals(True)
                spin.setValue(int(self._inherited[key]))
                spin.blockSignals(False)

    def _sync_order(self) -> None:
        """Each threshold floors the next: `normalise` would fix an inverted
        set silently, and a number that changes itself after Save reads as a
        bug."""
        floor = 1
        for key in FIELDS:
            spin = self.spins[key]
            spin.setMinimum(floor)
            floor = spin.value() + 1

    def entry(self) -> dict:

        if not self._own.isChecked():
            return {}
        return {key: int(self.spins[key].value()) for key in FIELDS}


def deck_controls(skin_switch, grade_switch, edit_button=None) -> QWidget:
    """The right-hand cells of a deck row, on a fixed grid so the header row
    built the same way lines its captions up with the switches."""
    from aqt.qt import QHBoxLayout

    wrap = QWidget()
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    for widget, width in ((skin_switch, 78), (grade_switch, 78),
                          (edit_button, 40)):
        cell = QWidget()
        cell.setFixedWidth(width)
        cell_box = QHBoxLayout(cell)
        cell_box.setContentsMargins(0, 0, 0, 0)
        cell_box.setSpacing(0)
        cell_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if widget is not None:
            cell_box.addWidget(widget)
        layout.addWidget(cell)
    return wrap
