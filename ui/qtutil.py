"""Small Qt helpers shared by the dialogs. No add-on state, no side effects."""

from aqt.qt import QLabel, QLineEdit, QPoint, Qt, QTimer, QToolTip, pyqtSignal


class AwdLineEdit(QLineEdit):
    """A line edit that can be read while an input method is still composing.

    A Vietnamese, Japanese or Chinese IME keeps the syllable being typed as
    *preedit*: it is painted inside the field, but `text()` does not return it
    until the composition ends — and clicking a button does not end one, because
    Qt buttons take no focus on click. "Type a name, press Save straight away"
    therefore read the field as **empty**: the habit editor refused, with no
    error and no way to guess why, and Settings would have saved a blank name.

    `QInputMethod.commit()` is not the fix. What it does to marked text is up to
    the platform plugin — the Cocoa one is as likely to discard the composition
    as to commit it — so a handler built on it can silently *lose* what the user
    typed. Recording the preedit from the events this widget already receives
    depends on no platform at all.

    Use `value()` wherever the text is read on the user's behalf; `text()` still
    means what it always did, and is right for anything watching as they type.
    """

    # `textEdited` stays silent for the whole of an IME composition, so
    # anything reacting to "the user is typing" — clearing a validation message,
    # enabling a button — has to listen here or it looks stuck to an IME user.
    valueEdited = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preedit = ""
        self.textEdited.connect(lambda _text: self.valueEdited.emit())

    def inputMethodEvent(self, event) -> None:
        super().inputMethodEvent(event)
        # A commit event carries an empty preedit, so this clears itself once
        # the composed text has landed in `text()`; the two never double up.
        self._preedit = event.preeditString()
        self.valueEdited.emit()

    def value(self) -> str:
        """Everything typed so far, committed or still being composed.

        Spliced at the cursor rather than appended: the preedit sits where the
        caret is, and composing in the middle of an existing name is rare but
        must not scramble it.
        """
        if not self._preedit:
            return self.text()
        text = self.text()
        at = max(0, min(self.cursorPosition(), len(text)))
        return text[:at] + self._preedit + text[at:]


class AwdInfoIcon(QLabel):
    """A small ⓘ that explains the row it sits in.

    Qt's tooltip wake-up delay is ~700 ms and is a style hint, not a setting,
    so this shows the tooltip itself on a short timer; passing `rect()` to
    `showText` stops Qt's own timer firing a second copy. A click shows it too,
    because a trackpad long-press never becomes a hover.

    Qt tooltips do not wrap on their own — pass `<br>` where a line should break.
    """

    DELAY_MS = 120

    def __init__(self, text: str, parent=None):
        super().__init__("i", parent)
        self.setObjectName("awdInfo")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setToolTip(text)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DELAY_MS)
        self._timer.timeout.connect(self._show)

    def _show(self) -> None:
        QToolTip.showText(self.mapToGlobal(QPoint(0, self.height())),
                          self.toolTip(), self, self.rect())

    def enterEvent(self, event) -> None:
        self._timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._timer.stop()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._timer.stop()
        self._show()
        super().mousePressEvent(event)
