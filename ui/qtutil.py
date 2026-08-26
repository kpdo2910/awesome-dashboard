"""Small Qt helpers shared by the dialogs. No add-on state, no side effects."""

from aqt.qt import QLineEdit, pyqtSignal


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
