"""FSRS integration.

Anki ships the FSRS scheduler natively (23.10+), so nothing here reimplements
it — this module just exposes the pieces the settings page drives: the global
on/off switch, each preset's desired retention, and parameter optimisation /
evaluation, all through Anki's own backend.

https://github.com/open-spaced-repetition/fsrs4anki
"""

from datetime import datetime

from aqt import mw

# Newest parameter slot first: Anki 26.x optimises FSRS-6, older collections
# may still carry v5 / v4 values.
PARAM_KEYS = ("fsrsParams6", "fsrsParams5", "fsrsWeights")


def available() -> bool:
    """False on Anki builds without the FSRS backend calls."""
    try:
        return hasattr(mw.col._backend, "compute_fsrs_params")
    except Exception:
        return False


# --- global switch ----------------------------------------------------------

def is_enabled() -> bool:
    try:
        return bool(mw.col.get_config("fsrs", default=False))
    except Exception:
        return False


def set_enabled(enabled: bool) -> None:
    """Flip FSRS the way Deck Options does.

    Going through `update_deck_configs` lets Anki (re)compute memory states for
    existing cards; poking the raw `fsrs` config key would leave the collection
    half-migrated. The current deck's limits are passed straight back so this
    round trip can't clobber them.
    """
    if is_enabled() == enabled:
        return
    try:
        from anki import deck_config_pb2 as pb

        deck_id = mw.col.decks.get_current_id()
        data = mw.col.decks.get_deck_configs_for_update(deck_id)
        mw.col.decks.update_deck_configs(
            pb.UpdateDeckConfigsRequest(
                target_deck_id=deck_id,
                configs=[entry.config for entry in data.all_config],
                mode=pb.UPDATE_DECK_CONFIGS_MODE_NORMAL,
                fsrs=enabled,
                card_state_customizer=data.card_state_customizer,
                limits=data.current_deck.limits,
                new_cards_ignore_review_limit=data.new_cards_ignore_review_limit,
                apply_all_parent_limits=data.apply_all_parent_limits,
                fsrs_reschedule=False,
                fsrs_health_check=data.fsrs_health_check,
            )
        )
    except Exception as e:
        print(f"[Awesome Dashboard] FSRS toggle via deck configs failed ({e}); writing raw key")
        try:
            mw.col.set_config("fsrs", enabled)
        except Exception as inner:
            print(f"[Awesome Dashboard] FSRS toggle failed: {inner}")


# --- presets ----------------------------------------------------------------

def presets() -> list:
    try:
        return sorted(mw.col.decks.all_config(), key=lambda c: str(c["name"]).lower())
    except Exception:
        return []


def preset(conf_id: int):
    for conf in presets():
        if int(conf["id"]) == int(conf_id):
            return conf
    return None


def save_preset(conf) -> None:
    mw.col.decks.update_config(conf)


def params(conf) -> list:
    for key in PARAM_KEYS:
        values = conf.get(key) or []
        if values:
            return list(values)
    return []


def param_key(conf) -> str:
    """Where freshly computed parameters belong for this collection."""
    for key in PARAM_KEYS:
        if key in conf:
            return key
    return PARAM_KEYS[0]


def desired_retention(conf) -> float:
    try:
        value = float(conf.get("desiredRetention", 0.9))
    except (TypeError, ValueError):
        return 0.9
    return min(0.99, max(0.70, value))


def days_since_optimize():
    """Days since Anki last optimised parameters, or None if unknown."""
    try:
        data = mw.col.decks.get_deck_configs_for_update(mw.col.decks.get_current_id())
        return int(data.days_since_last_fsrs_optimize)
    except Exception:
        return None


# --- optimisation inputs ----------------------------------------------------

def _search_for(conf) -> str:
    custom = str(conf.get("weightSearch") or "").strip()
    if custom:
        return custom
    name = str(conf.get("name", "")).replace("\\", "\\\\").replace('"', '\\"')
    return f'preset:"{name}"'


def _ignore_before_ms(conf) -> int:
    raw = str(conf.get("ignoreRevlogsBeforeDate") or "").strip()
    if not raw:
        return 0
    try:
        return int(datetime.strptime(raw, "%Y-%m-%d").timestamp() * 1000)
    except ValueError:
        return 0


def _relearn_steps(conf) -> int:
    try:
        return len(conf.get("lapse", {}).get("delays") or [])
    except Exception:
        return 0


# --- long-running backend calls --------------------------------------------

def optimize(conf_id: int) -> None:
    """Recompute this preset's parameters from its review history."""
    from aqt.operations import QueryOp
    from aqt.utils import showWarning, tooltip

    from ..core.translations import tr

    conf = preset(conf_id)
    if conf is None:
        return
    search = _search_for(conf)
    current = params(conf)
    ignore_before = _ignore_before_ms(conf)
    steps = _relearn_steps(conf)

    def op(col):
        return col._backend.compute_fsrs_params(
            search=search,
            current_params=current,
            ignore_revlogs_before_ms=ignore_before,
            num_of_relearning_steps=steps,
            health_check=False,
        )

    def success(response) -> None:
        new_params = [float(value) for value in response.params]
        target = preset(conf_id)
        if target is None:
            return
        if not new_params:
            # The backend answers with an empty list when the search matched
            # too little history to fit anything.
            tooltip(tr("fsrs_not_enough_data"), parent=mw, period=4000)
            return
        if new_params == params(target):
            tooltip(tr("fsrs_params_unchanged"), parent=mw)
            return
        target[param_key(target)] = new_params
        save_preset(target)
        tooltip(
            tr("fsrs_optimized", n=len(new_params),
               preset=target.get("name", "")),
            parent=mw,
            period=4000,
        )

    def failure(exc) -> None:
        showWarning(f"{tr('fsrs_optimize_failed')}\n\n{exc}", parent=mw)

    (
        QueryOp(parent=mw, op=op, success=success)
        .failure(failure)
        .with_progress(tr("fsrs_optimizing"))
        .run_in_background()
    )


def evaluate(conf_id: int) -> None:
    """Score the preset's current parameters against its review history."""
    from aqt.operations import QueryOp
    from aqt.utils import showInfo, showWarning

    from ..core.translations import tr

    conf = preset(conf_id)
    if conf is None:
        return
    search = _search_for(conf)
    ignore_before = _ignore_before_ms(conf)
    steps = _relearn_steps(conf)

    def op(col):
        return col._backend.evaluate_params(
            search=search,
            ignore_revlogs_before_ms=ignore_before,
            num_of_relearning_steps=steps,
        )

    def success(response) -> None:
        showInfo(
            tr("fsrs_evaluate_result",
               preset=conf.get("name", ""),
               loss=f"{response.log_loss:.4f}",
               rmse=f"{response.rmse_bins * 100:.2f}%"),
            parent=mw,
            title="FSRS",
        )

    def failure(exc) -> None:
        showWarning(f"{tr('fsrs_evaluate_failed')}\n\n{exc}", parent=mw)

    (
        QueryOp(parent=mw, op=op, success=success)
        .failure(failure)
        .with_progress(tr("fsrs_evaluating"))
        .run_in_background()
    )
