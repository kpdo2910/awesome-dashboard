"""Theme picker: a row of accent swatches plus a colour editor dialog.

The swatches choose the built-in theme; the editor replaces only the accent
family, leaving backgrounds, text and the new/learn/due colours to the theme.
"""

from aqt.qt import (
    QAbstractButton,
    QColor,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..core import themes
from ..core.translations import tr

# Order shown in the picker and the editor's preset grid.
THEME_ORDER = ["glass", "terracotta", "matcha", "ajisai", "sakura", "sumi"]

# Editable slots, in the order they appear in the editor.
COLOR_ROWS = [
    ("accent", "color_accent"),
    ("accent-soft", "color_soft"),
    ("accent-hover", "color_hover"),
    ("on-accent", "color_on_accent"),
]


def theme_label(key: str) -> str:
    """"Terracotta" out of "Terracotta — warm paper"."""
    return tr(f"theme_{key}").split("—")[0].strip()


def _readable_on(color: str) -> str:
    return themes.derive_accents(color).get("on-accent", "#ffffff")


class _Swatch(QAbstractButton):
    """A filled circle; the selected one gains a ring and a checkmark."""

    DIAMETER = 34
    RING_GAP = 4
    RING_WIDTH = 3

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        size = self.DIAMETER + 2 * (self.RING_GAP + self.RING_WIDTH)
        self.setFixedSize(QSize(size, size))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # QPointF, so the float radii below pick the right drawEllipse overload.
        center = QPointF(self.rect().center())
        fill = QColor(self.color)
        radius = self.DIAMETER / 2

        if self.isChecked():
            pen = QPen(fill)
            pen.setWidthF(self.RING_WIDTH)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            outer = radius + self.RING_GAP + self.RING_WIDTH / 2
            painter.drawEllipse(center, outer, outer)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(center, radius, radius)

        if self.isChecked():
            tick = QPainterPath()
            tick.moveTo(center.x() - 6.5, center.y() + 0.5)
            tick.lineTo(center.x() - 1.5, center.y() + 5.5)
            tick.lineTo(center.x() + 7.0, center.y() - 4.5)
            pen = QPen(QColor(_readable_on(self.color)))
            pen.setWidthF(2.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(tick)


class _ColorButton(QPushButton):
    """A small filled rectangle that opens a colour picker.

    Tint slots (soft, hover) are drawn at their true opacity over the card behind
    them, so the row shows the real colour instead of four identical blocks.
    """

    def __init__(self, color: str, alpha: float = 1.0, backdrop: str = "#2a2a2e",
                 parent=None):
        super().__init__(parent)
        self.setObjectName("awdColorChip")
        self.setFixedSize(QSize(44, 30))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alpha = alpha
        self._backdrop = backdrop
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        if not self._color.isValid():
            self._color = QColor("#000000")
        shown = self._color.name()
        if self._alpha < 1.0:
            try:
                from . import qt_theme

                shown = qt_theme.flatten(
                    f"rgba({self._color.red()}, {self._color.green()},"
                    f" {self._color.blue()}, {self._alpha})",
                    self._backdrop,
                )
            except Exception:
                pass
        self.setStyleSheet(
            f"#awdColorChip {{ background: {shown};"
            " border: 1px solid rgba(128,128,128,0.45); border-radius: 7px; }"
        )

    def color_hex(self) -> str:
        return self._color.name().upper()

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(self._color, self, tr("pick_color"))
        if chosen.isValid():
            self.set_color(chosen.name())
            self.clicked_color()

    def clicked_color(self) -> None:
        """Overridden by the dialog to react to a new colour."""


class ThemeEditorDialog(QDialog):
    """Quick presets on top, the four accent slots below."""

    def __init__(self, theme: str, accent: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("theme_editor_title"))
        self.setModal(True)
        self.setMinimumWidth(430)
        try:
            from . import qt_theme

            self.setStyleSheet(qt_theme.settings_dialog_qss())
        except Exception:
            pass

        self._theme_for_backdrop = theme
        values = dict(themes.derive_accents(themes.theme_accent(theme)))
        values.update({k: v for k, v in (accent or {}).items() if v})
        self._values = values

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(16)

        layout.addWidget(self._presets_group())
        layout.addWidget(self._colors_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Reset
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.button(QDialogButtonBox.StandardButton.Reset).setText(
            tr("reset_theme_colors")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setText(tr("apply"))
        apply_button.setObjectName("awdPrimary")
        apply_button.setDefault(True)
        apply_button.clicked.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(
            self._reset
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._theme = theme
        self._was_reset = False

    # --- sections ---

    def _card(self, title: str) -> tuple:
        card = QWidget()
        card.setObjectName("awdGroup")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(card)
        box.setContentsMargins(14, 12, 14, 14)
        box.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("awdRowTitle")
        box.addWidget(heading)
        return card, box

    def _presets_group(self) -> QWidget:
        card, box = self._card(tr("quick_presets"))
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, key in enumerate(THEME_ORDER):
            accent = themes.theme_accent(key)
            button = QPushButton(theme_label(key))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(38)
            button.setStyleSheet(
                f"QPushButton {{ background: {accent}; color: {_readable_on(accent)};"
                " border: none; border-radius: 8px; font-weight: 700; }"
                f"QPushButton:hover {{ background: {accent}; }}"
            )
            button.clicked.connect(lambda _c, k=key: self._use_preset(k))
            grid.addWidget(button, index // 3, index % 3)
        box.addLayout(grid)
        return card

    def _colors_group(self) -> QWidget:
        card, box = self._card(tr("custom_colors"))
        self._chips = {}
        self._hex_labels = {}
        for key, label_key in COLOR_ROWS:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(tr(label_key))
            label.setObjectName("awdRowTitle")
            row.addWidget(label, 1)

            alpha = {"accent-soft": 0.14, "accent-hover": 0.24}.get(key, 1.0)
            chip = _ColorButton(self._solid(key), alpha, self._backdrop())
            chip.clicked_color = lambda k=key: self._chip_changed(k)
            self._chips[key] = chip
            row.addWidget(chip)

            hex_label = QLabel(self._hex_text(key, chip.color_hex()))
            hex_label.setObjectName("awdRowSub")
            hex_label.setMinimumWidth(74)
            self._hex_labels[key] = hex_label
            row.addWidget(hex_label)
            box.addLayout(row)

        note = QLabel(tr("colors_apply_both"))
        note.setObjectName("awdRowSub")
        note.setWordWrap(True)
        box.addWidget(note)
        return card

    # --- behaviour ---

    def _backdrop(self) -> str:
        """The card colour the tint chips are composited over."""
        try:
            from aqt.theme import theme_manager

            from . import qt_theme

            pal = themes.palette(self._theme_for_backdrop, theme_manager.night_mode)
            return qt_theme.flatten(pal["surface"], pal["bg"])
        except Exception:
            return "#2a2a2e"

    def _hex_text(self, key: str, hex_value: str) -> str:
        alpha = {"accent-soft": 14, "accent-hover": 24}.get(key)
        return f"{hex_value} · {alpha}%" if alpha else hex_value

    def _solid(self, key: str) -> str:
        """A pickable hex for a slot; the soft/hover tints show as their base."""
        value = self._values.get(key, "")
        if value.startswith("rgba"):
            parts = value[value.index("(") + 1:value.index(")")].split(",")
            try:
                r, g, b = (int(float(p)) for p in parts[:3])
                return "#%02x%02x%02x" % (r, g, b)
            except ValueError:
                return "#000000"
        return value or "#000000"

    def _sync_chips(self) -> None:
        for key, chip in self._chips.items():
            chip.set_color(self._solid(key))
            self._hex_labels[key].setText(self._hex_text(key, chip.color_hex()))

    def _use_preset(self, key: str) -> None:
        self._values = dict(themes.derive_accents(themes.theme_accent(key)))
        self._theme = key
        self._sync_chips()

    def _chip_changed(self, key: str) -> None:
        color = self._chips[key].color_hex()
        if key == "accent":
            # Picking the main colour re-derives the rest; each can still be
            # fine-tuned afterwards.
            self._values = dict(themes.derive_accents(color))
            self._sync_chips()
            return
        if key in ("accent-soft", "accent-hover"):
            alpha = 0.14 if key == "accent-soft" else 0.24
            rgb = themes._rgb(color)
            if rgb:
                self._values[key] = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"
        else:
            self._values[key] = color
        self._chips[key].set_color(color)
        self._hex_labels[key].setText(self._hex_text(key, color))

    def _reset(self) -> None:
        self._was_reset = True
        self.accept()

    # --- result ---

    def result_theme(self) -> str:
        return self._theme

    def result_accent(self):
        """The accent override, or None when the theme's own colours are fine."""
        if self._was_reset:
            return None
        default = themes.derive_accents(themes.theme_accent(self._theme))
        if self._values == default:
            return None
        return dict(self._values)


class ThemePicker(QWidget):
    """Swatch row with the theme names underneath, plus the editor button."""

    def __init__(self, theme: str, accent: dict, parent=None):
        super().__init__(parent)
        self._theme = theme if theme in THEME_ORDER else "glass"
        self._accent = dict(accent or {})

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)

        hint = QLabel(tr("theme_section_hint"))
        hint.setObjectName("awdRowSub")
        hint.setWordWrap(True)
        box.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._swatches = {}
        for key in THEME_ORDER:
            column = QVBoxLayout()
            column.setSpacing(2)
            swatch = _Swatch(self._swatch_color(key))
            swatch.setChecked(key == self._theme)
            swatch.clicked.connect(lambda _c, k=key: self._select(k))
            self._swatches[key] = swatch
            column.addWidget(swatch, 0, Qt.AlignmentFlag.AlignHCenter)
            name = QLabel(theme_label(key))
            name.setObjectName("awdRowSub")
            name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(name)
            row.addLayout(column)
        row.addStretch(1)
        box.addLayout(row)

        edit = QPushButton(tr("edit_theme") + "  ✎")
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.clicked.connect(self._open_editor)
        edit_row = QHBoxLayout()
        edit_row.addWidget(edit)
        edit_row.addStretch(1)
        box.addLayout(edit_row)

    def _swatch_color(self, key: str) -> str:
        # The selected theme previews the custom accent, if there is one.
        if key == self._theme and self._accent.get("accent"):
            return self._accent["accent"]
        return themes.theme_accent(key)

    def _select(self, key: str) -> None:
        self._theme = key
        # A custom accent belongs to the theme it was made for.
        self._accent = {}
        self._refresh()

    def _refresh(self) -> None:
        for key, swatch in self._swatches.items():
            swatch.color = self._swatch_color(key)
            swatch.setChecked(key == self._theme)
            swatch.update()

    def _open_editor(self) -> None:
        dialog = ThemeEditorDialog(self._theme, self._accent, self)
        if dialog.exec():
            self._theme = dialog.result_theme()
            self._accent = dialog.result_accent() or {}
            self._refresh()

    # --- result ---

    def theme(self) -> str:
        return self._theme

    def accent(self):
        return dict(self._accent) or None
