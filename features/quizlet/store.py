"""Records, resumable sessions and the field map, in collection config.

The only module in this package that touches the collection, and the reason
the other three do not: `tools/test_quizlet.py` loads them directly.

Everything here is user data, so it goes in `col.set_config` rather than the
add-on config — `meta.json` is merged against `config.json` on every add-on
update, and a Match record or a half-finished Learn session put there would
quietly disappear the next time the add-on was upgraded. Collection config
rides along in `.colpkg` backups and in sync, next to `awd_habits_*` and
`awd_heatmap_scale`.

    awd_qz_records    {deck id: {"match": secs, "test": percent, "at": day}}
    awd_qz_sessions   {deck id: <session dict from session.py>}
    awd_qz_fieldmap   {notetype id: {"front": [...], "back": [...]}}

Writes are debounced: a Learn answer saves the session, and answering seven
terms in a round should be one write rather than seven. Every exit path
flushes — see `install_hooks`.
"""

RECORDS_KEY = "awd_qz_records"
SESSIONS_KEY = "awd_qz_sessions"
FIELDMAP_KEY = "awd_qz_fieldmap"

# Same delay as the habit store, for the same reason: long enough to collapse a
# burst, short enough that no realistic answer-then-quit beats it.
WRITE_DELAY_MS = 400

# Sessions are kept per deck; a user who cycles through many decks should not
# accumulate them forever. Oldest goes first once the map is this long.
MAX_SESSIONS = 24


def _sides(pinned: dict) -> dict:
    """Read one note type's pin, in whichever shape it was written.

    Two earlier shapes existed in development builds: one field per side
    (`term`/`def`), and one entry per *card template* keyed by ordinal. Both are
    renamed on read rather than migrated in a pass — dropping them silently
    would reset the one setting a user had bothered to change. The per-template
    shape collapses to whichever template sorts first, because a study mode now
    takes one card per note and there is nothing left to key on.
    """
    if not isinstance(pinned, dict):
        return {}
    if "front" in pinned or "back" in pinned:
        return {
            key: [str(name) for name in pinned[key] if name]
            for key in ("front", "back")
            if isinstance(pinned.get(key), list)
        }
    if pinned.get("term") or pinned.get("def"):
        moved = {}
        if pinned.get("term"):
            moved["front"] = [str(pinned["term"])]
        if pinned.get("def"):
            moved["back"] = [str(pinned["def"])]
        return moved
    for key in sorted(pinned, key=lambda item: str(item)):
        nested = _sides(pinned[key])
        if nested:
            return nested
    return {}


class QuizletStore:
    def __init__(self):
        self._cache = {}
        self._dirty = set()
        self._timer = None

    # --- collection access ---

    def _col(self):
        from aqt import mw

        return mw.col

    def _read(self, key: str) -> dict:
        col = self._col()
        if col is None:
            return {}
        try:
            value = col.get_config(key, None)
        except Exception as e:
            print(f"[Awesome Dashboard] quizlet: cannot read {key}: {e}")
            return {}
        return value if isinstance(value, dict) else {}

    def _blob(self, key: str) -> dict:
        if key not in self._cache:
            self._cache[key] = self._read(key)
        return self._cache[key]

    def _touch(self, key: str) -> None:
        self._dirty.add(key)
        self._schedule()

    def _schedule(self) -> None:
        from aqt.qt import QTimer

        if self._timer is None:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.flush)
        self._timer.start(WRITE_DELAY_MS)

    def flush(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        pending, self._dirty = self._dirty, set()
        col = self._col()
        if col is None:
            return
        for key in pending:
            try:
                # `undoable` stays False: finishing a round of Learn has nothing
                # to do with the review queue, and letting it into the undo
                # stack means Ctrl+Z after answering a card rewinds a session.
                col.set_config(key, self._cache.get(key, {}))
            except Exception as e:
                print(f"[Awesome Dashboard] quizlet: cannot write {key}: {e}")

    def reset(self) -> None:
        """Drop the cache *without* writing — only once pending writes are gone
        or deliberately abandoned."""
        if self._timer is not None:
            self._timer.stop()
        self._dirty.clear()
        self._cache.clear()

    def invalidate(self) -> None:
        self.flush()
        self.reset()

    # --- records ---

    def record(self, deck_id: int) -> dict:
        entry = self._blob(RECORDS_KEY).get(str(int(deck_id)))
        return entry if isinstance(entry, dict) else {}

    def save_record(self, deck_id: int, kind: str, value: float) -> bool:
        """Keep the best only. Returns whether this beat what was there.

        "Best" runs the other way for the two kinds — the fastest Match and the
        highest Test — so the comparison is named rather than inferred.
        """
        records = self._blob(RECORDS_KEY)
        key = str(int(deck_id))
        entry = dict(records.get(key) or {})
        old = entry.get(kind)
        better = old is None or (
            float(value) < float(old) if kind == "match" else float(value) > float(old)
        )
        if not better:
            return False
        entry[kind] = round(float(value), 1)
        records[key] = entry
        self._touch(RECORDS_KEY)
        return True

    # --- sessions ---

    def session(self, deck_id: int) -> dict:
        entry = self._blob(SESSIONS_KEY).get(str(int(deck_id)))
        return entry if isinstance(entry, dict) else None

    def save_session(self, deck_id: int, state: dict) -> None:
        sessions = self._blob(SESSIONS_KEY)
        key = str(int(deck_id))
        # Deleted before it is re-added so insertion order stays *use* order:
        # assigning to an existing key leaves it where it was, which would let
        # the eviction below throw away the session being played.
        sessions.pop(key, None)
        sessions[key] = state
        for stale in list(sessions)[:max(0, len(sessions) - MAX_SESSIONS)]:
            del sessions[stale]
        self._touch(SESSIONS_KEY)

    def clear_session(self, deck_id: int) -> None:
        sessions = self._blob(SESSIONS_KEY)
        if sessions.pop(str(int(deck_id)), None) is not None:
            self._touch(SESSIONS_KEY)

    # --- field map ---

    def field_map(self, notetype_id: int) -> dict:
        """{"front": [names], "back": [names]} pinned for one note type.

        Per note type, not per card template: a study mode takes one card per
        note, so the second template of a two-card note type never reaches it
        and a setting keyed to that template would be a control with nothing
        behind it.

        A side the user has not pinned is absent rather than empty, because
        those mean different things: absent falls back to the automatic guess,
        while an empty list is "show nothing on this side" and would leave a
        card with no question.
        """
        return _sides(self._blob(FIELDMAP_KEY).get(str(int(notetype_id))))

    def set_field_map(self, notetype_id: int, front, back) -> None:
        """Pin the fields for one note type. Two empty sides clear it."""
        blob = self._blob(FIELDMAP_KEY)
        key = str(int(notetype_id))
        front = [str(name) for name in (front or []) if name]
        back = [str(name) for name in (back or []) if name]
        if front or back:
            blob[key] = {"front": front, "back": back}
        else:
            blob.pop(key, None)
        self._touch(FIELDMAP_KEY)


_store = None


def get_store() -> QuizletStore:
    global _store
    if _store is None:
        _store = QuizletStore()
    return _store


def flush() -> None:
    if _store is not None:
        _store.flush()


def invalidate() -> None:
    if _store is not None:
        _store.invalidate()


def reset() -> None:
    if _store is not None:
        _store.reset()


def install_hooks() -> None:
    """Same contract as the habit store — see its `install_hooks` for why.

    In short: flush on the way out and before a sync, and *drop* rather than
    flush after one, because a sync replaces these keys wholesale with another
    device's copy and writing a stale cache back over it would undo the sync.
    """
    from aqt import gui_hooks

    def on_close(*_args):
        invalidate()

    def on_sync_start(*_args):
        flush()

    def on_drop(*_args):
        reset()

    for name, handler in (
        ("profile_will_close", on_close),
        ("sync_will_start", on_sync_start),
        ("sync_did_finish", on_drop),
        ("profile_did_open", on_drop),
    ):
        hook = getattr(gui_hooks, name, None)
        if hook is None:
            print(f"[Awesome Dashboard] quizlet: no gui_hooks.{name} on this Anki")
            continue
        hook.append(handler)
