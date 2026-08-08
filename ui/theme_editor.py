"""Theme picker: a row of accent swatches plus a colour editor dialog.

The swatches choose the built-in theme; the editor replaces only the accent
family, leaving backgrounds, text and the new/learn/due colours to the theme.
"""

import math

from aqt.qt import (
    QAbstractButton,
    QCheckBox,
    QColor,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QSize,
    QSpinBox,
    Qt,
    QVBoxLayout,
    QWidget,
)

from ..core import themes
from ..core.translations import tr

# Order shown in the picker and the editor's preset grid.
THEME_ORDER = ["glass", "terracotta", "matcha", "aurora", "sunset", "sakura"]

# Editable slots, in the order they appear in the editor. "accent" is hidden
# while a gradient is on, because it is then the midpoint of the two stops.
COLOR_ROWS = [
    ("accent", "color_accent"),
    ("accent-soft", "color_soft"),
    ("accent-hover", "color_hover"),
    ("on-accent", "color_on_accent"),
]

# Hue distance to the second stop when a solid accent is first made a gradient.
DEFAULT_HUE_SHIFT = 40


def theme_label(key: str) -> str:
    """"Terracotta" out of "Terracotta — warm paper"."""
    return tr(f"theme_{key}").split("—")[0].strip()


def _readable_on(color: str) -> str:
    return themes.derive_accents(color).get("on-accent", "#ffffff")


def theme_family(key: str) -> dict:
    """A theme's accent family as the editor models it.

    Derived rather than read off the palette so that opening the editor and
    applying without touching anything compares equal, and so saves no override.
    """
    gradient = themes.theme_gradient(key)
    if gradient:
        return themes.derive_gradient(*gradient)
    return themes.derive_accents(themes.theme_accent(key))


def _gradient_points(angle: int) -> tuple:
    """CSS angle to (x1, y1, x2, y2) as fractions of the box, y growing down."""
    radians = math.radians(angle)
    dx, dy = math.sin(radians), -math.cos(radians)
    return (0.5 - dx / 2, 0.5 - dy / 2, 0.5 + dx / 2, 0.5 + dy / 2)


def _linear_gradient(rect, gradient: tuple) -> QLinearGradient:
    start, end, angle = gradient
    x1, y1, x2, y2 = _gradient_points(angle)
    brush = QLinearGradient(
        QPointF(rect.x() + x1 * rect.width(), rect.y() + y1 * rect.height()),
        QPointF(rect.x() + x2 * rect.width(), rect.y() + y2 * rect.height()),
    )
    brush.setColorAt(0.0, QColor(start))
    brush.setColorAt(1.0, QColor(end))
    return brush


def _qss_gradient(gradient: tuple) -> str:
    start, end, angle = gradient
    x1, y1, x2, y2 = _gradient_points(angle)
    return (
        f"qlineargradient(x1:{x1:.3f}, y1:{y1:.3f}, x2:{x2:.3f}, y2:{y2:.3f},"
        f" stop:0 {start}, stop:1 {end})"
    )


class _Swatch(QAbstractButton):
    """A filled circle; the selected one gains a ring and a checkmark.

    `gradient` is an optional (start, end, angle); `color` stays the solid
    stand-in used for the ring and the tick, which need one colour each.
    """

    DIAMETER = 34
    RING_GAP = 4
    RING_WIDTH = 3

    def __init__(self, color: str, gradient=None, parent=None):
        super().__init__(parent)
        self.color = color
        self.gradient = gradient
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
        if self.gradient:
            disc = self.rect().adjusted(
                self.RING_GAP + self.RING_WIDTH, self.RING_GAP + self.RING_WIDTH,
                -(self.RING_GAP + self.RING_WIDTH), -(self.RING_GAP + self.RING_WIDTH),
            )
            painter.setBrush(_linear_gradient(disc, self.gradient))
        else:
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
        values = dict(theme_family(theme))
        values.update({k: v for k, v in (accent or {}).items() if v})
        self._values = values
        # The gradient is stored as a CSS string; the editor works in its parts.
        self._gradient = themes.parse_gradient(values.get("accent-grad", ""))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(16)

        self._grad_rows = []
        layout.addWidget(self._presets_group())
        layout.addWidget(self._gradient_group())
        layout.addWidget(self._colors_group())
        self._sync_gradient_ui()

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
            gradient = themes.theme_gradient(key)
            brush = _qss_gradient(gradient) if gradient else accent
            button = QPushButton(theme_label(key))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(38)
            button.setStyleSheet(
                f"QPushButton {{ background: {brush}; color: {_readable_on(accent)};"
                " border: none; border-radius: 8px; font-weight: 700; }"
                f"QPushButton:hover {{ background: {brush}; }}"
            )
            button.clicked.connect(lambda _c, k=key: self._use_preset(k))
            grid.addWidget(button, index // 3, index % 3)
        box.addLayout(grid)
        return card

    def _labelled_row(self, text: str, *widgets) -> QWidget:
        """A row as a widget rather than a layout, so it can be hidden.

        Takes translated text, not a key, so tools/check_locales.py can still
        see every literal tr() call at the call site.
        """
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(text)
        label.setObjectName("awdRowTitle")
        layout.addWidget(label, 1)
        for widget in widgets:
            layout.addWidget(widget)
        return row

    def _gradient_group(self) -> QWidget:
        card, box = self._card(tr("gradient"))

        self._grad_switch = QCheckBox()
        self._grad_switch.setChecked(self._gradient is not None)
        self._grad_switch.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grad_switch.toggled.connect(self._gradient_toggled)
        box.addWidget(self._labelled_row(tr("gradient_use"), self._grad_switch))

        start, end, angle = self._gradient_parts()
        self._grad_chips = {}
        for key, label, value in (
            ("start", tr("gradient_from"), start),
            ("end", tr("gradient_to"), end),
        ):
            chip = _ColorButton(value, 1.0, self._backdrop())
            chip.clicked_color = lambda k=key: self._gradient_chip_changed(k)
            self._grad_chips[key] = chip
            hex_label = QLabel(chip.color_hex())
            hex_label.setObjectName("awdRowSub")
            hex_label.setMinimumWidth(74)
            self._grad_chips[key + "_hex"] = hex_label
            self._grad_rows.append(self._labelled_row(label, chip, hex_label))
            box.addWidget(self._grad_rows[-1])

        self._angle_box = QSpinBox()
        self._angle_box.setRange(0, 359)
        self._angle_box.setSingleStep(15)
        self._angle_box.setSuffix("°")
        self._angle_box.setValue(angle)
        self._angle_box.valueChanged.connect(self._gradient_changed)
        angle_row = self._labelled_row(tr("gradient_angle"), self._angle_box)
        self._grad_rows.append(angle_row)
        box.addWidget(angle_row)

        self._preview = QFrame()
        self._preview.setFixedHeight(38)
        self._grad_rows.append(self._preview)
        box.addWidget(self._preview)

        hint = QLabel(tr("gradient_hint"))
        hint.setObjectName("awdRowSub")
        hint.setWordWrap(True)
        box.addWidget(hint)
        return card

    def _colors_group(self) -> QWidget:
        card, box = self._card(tr("custom_colors"))
        self._chips = {}
        self._hex_labels = {}
        self._color_rows = {}
        for key, label_key in COLOR_ROWS:
            alpha = {"accent-soft": 0.14, "accent-hover": 0.24}.get(key, 1.0)
            chip = _ColorButton(self._solid(key), alpha, self._backdrop())
            chip.clicked_color = lambda k=key: self._chip_changed(k)
            self._chips[key] = chip

            hex_label = QLabel(self._hex_text(key, chip.color_hex()))
            hex_label.setObjectName("awdRowSub")
            hex_label.setMinimumWidth(74)
            self._hex_labels[key] = hex_label

            row = self._labelled_row(tr(label_key), chip, hex_label)
            self._color_rows[key] = row
            box.addWidget(row)

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

    # --- gradient ---

    def _gradient_parts(self) -> tuple:
        """(start, end, angle) to show — invented from the accent when off."""
        if self._gradient:
            return self._gradient
        accent = self._solid("accent")
        return (accent, themes.shift_hue(accent, DEFAULT_HUE_SHIFT),
                themes.GRADIENT_ANGLE)

    def _sync_gradient_ui(self) -> None:
        on = self._gradient is not None
        for row in self._grad_rows:
            row.setVisible(on)
        # With a gradient the accent is the midpoint of the two stops, so an
        # editable accent row would offer a value the gradient overrules.
        self._color_rows["accent"].setVisible(not on)

        start, end, angle = self._gradient_parts()
        self._grad_chips["start"].set_color(start)
        self._grad_chips["end"].set_color(end)
        self._grad_chips["start_hex"].setText(self._grad_chips["start"].color_hex())
        self._grad_chips["end_hex"].setText(self._grad_chips["end"].color_hex())
        if self._angle_box.value() != angle:
            self._angle_box.blockSignals(True)
            self._angle_box.setValue(angle)
            self._angle_box.blockSignals(False)
        self._preview.setStyleSheet(
            f"background: {_qss_gradient((start, end, angle))};"
            " border-radius: 9px;"
        )
        self.adjustSize()

    def _gradient_toggled(self, on: bool) -> None:
        if on:
            self._gradient = self._gradient_parts()
            self._values = dict(themes.derive_gradient(*self._gradient))
        else:
            self._gradient = None
            # Keep the midpoint as the solid accent, so turning the gradient off
            # lands on the colour the user was already looking at.
            self._values = dict(themes.derive_accents(self._solid("accent")))
        self._sync_chips()
        self._sync_gradient_ui()

    def _gradient_chip_changed(self, which: str) -> None:
        start, end, angle = self._gradient_parts()
        color = self._grad_chips[which].color_hex()
        self._gradient = (
            (color, end, angle) if which == "start" else (start, color, angle)
        )
        self._gradient_changed()

    def _gradient_changed(self, *_args) -> None:
        start, end, _ = self._gradient_parts()
        self._gradient = (start, end, self._angle_box.value())
        self._values = dict(themes.derive_gradient(*self._gradient))
        self._sync_chips()
        self._sync_gradient_ui()

    def _use_preset(self, key: str) -> None:
        self._values = dict(theme_family(key))
        self._gradient = themes.parse_gradient(self._values.get("accent-grad", ""))
        self._theme = key
        self._grad_switch.blockSignals(True)
        self._grad_switch.setChecked(self._gradient is not None)
        self._grad_switch.blockSignals(False)
        self._sync_chips()
        self._sync_gradient_ui()

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
        if self._values == theme_family(self._theme):
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
            swatch = _Swatch(self._swatch_color(key), self._swatch_gradient(key))
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

    def _swatch_gradient(self, key: str):
        if key == self._theme and self._accent:
            # A custom accent replaces the family whole, so a solid override
            # must show as solid even on a theme that ships a gradient.
            return themes.parse_gradient(self._accent.get("accent-grad", ""))
        return themes.theme_gradient(key)

    def _select(self, key: str) -> None:
        self._theme = key
        # A custom accent belongs to the theme it was made for.
        self._accent = {}
        self._refresh()

    def _refresh(self) -> None:
        for key, swatch in self._swatches.items():
            swatch.color = self._swatch_color(key)
            swatch.gradient = self._swatch_gradient(key)
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
