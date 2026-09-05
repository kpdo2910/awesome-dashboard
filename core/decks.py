"""Deck identity helpers shared by the per-deck features. One walk, root
first; the caller reverses if it wants the nearest deck first."""

from aqt import mw


def chain_ids(did: int) -> list:
    """The deck and its ancestors, **root first**.

    By name, because that is the only parent relationship Anki stores.
    """
    ids = []
    try:
        parts = mw.col.decks.name(did).split("::")
        for depth in range(1, len(parts) + 1):
            candidate = mw.col.decks.id_for_name("::".join(parts[:depth]))
            if candidate:
                ids.append(int(candidate))
    except Exception:
        ids = []
    return ids or [int(did)]


def deck_id_for_card(card) -> int:
    """The deck the card is filed in, not the filtered deck it is seen in."""
    try:
        return int(card.current_deck_id())
    except Exception:
        return int(getattr(card, "odid", 0) or card.did)
