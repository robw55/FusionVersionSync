# Fusion 360 Python add-in: Sync a user parameter with the active file's cloud version.


import adsk.core, adsk.fusion, adsk.cam, traceback
import time

_app = None
_ui = None
_handlers = []  # keep handler references so they are not GC'd
_last_known_version = None

PARAM_NAME = 'FusionVersion'  # change if you prefer a different parameter name


def get_active_design():
    app = adsk.core.Application.get()
    return adsk.fusion.Design.cast(app.activeProduct)


def get_datafile_version(doc: adsk.core.Document) -> int:
    """
    Returns the cloud DataFile version number for the document.
    If unavailable (unsaved or local/temp), returns 0.
    """
    try:
        data_file = doc.dataFile
        if data_file:
            return int(data_file.versionNumber)
    except:
        pass
    return 0


def _normalize_numeric_expr(value):
    """
    Convert a numeric value to a simple, non-scientific expression string Fusion accepts.
    Returns (expr_string, float_value) or (None, None) if not numeric.
    """
    try:
        f = float(value)
    except:
        return None, None

    # Reject NaN or infinities
    if f != f or f == float('inf') or f == float('-inf'):
        return None, None

    # If integer-like, return integer string
    if float(f).is_integer():
        return str(int(f)), float(f)

    # Otherwise format with fixed-point, trim trailing zeros
    expr = ('{0:.6f}'.format(f)).rstrip('0').rstrip('.')
    if expr == '':
        expr = '0'
    return expr, f


def ensure_user_parameter(des, name, value):
    """
    Ensure a dimensionless user parameter exists and matches `value`.
    Defensive: validates numeric input, avoids scientific notation, and falls back
    to createByReal if createByString fails.
    """
    try:
        # Basic guards
        if not des:
            return
        up = getattr(des, 'userParameters', None)
        if not up:
            return

        existing = up.itemByName(name)
        unit_type = "NoUnits"  # version numbers are dimensionless

        expr, float_val = _normalize_numeric_expr(value)
        if expr is None:
            # Nothing sensible to set; skip quietly
            return

        if existing:
            try:
                existing.expression = expr
                return
            except Exception:
                # Fall through to attempt re-adding if update fails
                pass

        # Try to add using a string expression first
        try:
            val_input = adsk.core.ValueInput.createByString(expr)
            up.add(name, val_input, unit_type, 'Active file version')
            return
        except Exception:
            # If createByString fails, try createByReal as a fallback
            try:
                if float_val is None:
                    # Shouldn't happen, but guard anyway
                    float_val = float(expr)
                val_input = adsk.core.ValueInput.createByReal(float_val)
                up.add(name, val_input, unit_type, 'Active file version')
                return
            except Exception:
                # Give up silently (but log to UI for debugging)
                try:
                    ui = adsk.core.Application.get().userInterface
                    ui.messageBox('FusionVersionSync: failed to add/update parameter "{}" with value "{}".\n\n{}'.format(
                        name, expr, traceback.format_exc()))
                except:
                    pass
                return

    except:
        # If something unexpected happens, surface a message so you can debug
        try:
            ui = adsk.core.Application.get().userInterface
            ui.messageBox('FusionVersionSync ensure_user_parameter error:\n{}'.format(traceback.format_exc()))
        except:
            pass
        return


def sync_version_parameter():
    """
    Read the active document's cloud version and ensure the user parameter is set.
    This function is safe to call from event handlers; it will quietly return
    if there is no active design context.
    """
    app = adsk.core.Application.get()
    if not app:
        return

    # Guard: activeDocument may be None during startup or when no doc is open
    try:
        doc = app.activeDocument
    except:
        return

    if not doc:
        return

    des = get_active_design()
    # Skip if the active product isn't a Fusion Design (e.g., Drawing, CAM)
    if not des or not isinstance(des, adsk.fusion.Design):
        return

    version_num = get_datafile_version(doc)
    ensure_user_parameter(des, PARAM_NAME, version_num)


class DocumentActivatedHandler(adsk.core.DocumentEventHandler):
    def notify(self, args):
        try:
            sync_version_parameter()
        except:
            _ui = adsk.core.Application.get().userInterface
            _ui.messageBox('Error syncing version parameter on activate:\n{}'.format(traceback.format_exc()))


class DocumentSavingHandler(adsk.core.DocumentEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            doc = None
            try:
                doc = app.activeDocument
            except:
                doc = None

            global _last_known_version
            _last_known_version = 0
            if doc and doc.dataFile:
                try:
                    _last_known_version = int(doc.dataFile.versionNumber)
                except:
                    _last_known_version = 0
        except:
            _ui = adsk.core.Application.get().userInterface
            _ui.messageBox('Error in DocumentSavingHandler:\n{}'.format(traceback.format_exc()))


class DocumentSavedHandler(adsk.core.DocumentEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            doc = None
            try:
                doc = app.activeDocument
            except:
                doc = None

            global _last_known_version

            # If no doc or no dataFile (local/unsaved), do a best-effort sync and return
            if not doc or not doc.dataFile:
                try:
                    sync_version_parameter()
                except:
                    ui.messageBox('Error syncing version parameter after save (no dataFile):\n{}'.format(traceback.format_exc()))
                return

            # Two-phase polling:
            # Phase 1: quick checks (fast response when cloud is quick)
            fast_tries = 8
            for i in range(fast_tries):
                try:
                    current = int(doc.dataFile.versionNumber)
                except:
                    current = 0

                if current > (_last_known_version or 0):
                    sync_version_parameter()
                    _last_known_version = current
                    return

                adsk.doEvents()  # yield to Fusion

            # Phase 2: slower checks with small sleep to allow cloud to catch up
            slow_tries = 30
            sleep_interval = 0.12  # 120 ms; tune if needed
            for i in range(slow_tries):
                try:
                    current = int(doc.dataFile.versionNumber)
                except:
                    current = 0

                if current > (_last_known_version or 0):
                    sync_version_parameter()
                    _last_known_version = current
                    return

                adsk.doEvents()
                time.sleep(sleep_interval)

            # Final best-effort sync if we never saw the increment
            sync_version_parameter()

        except:
            _ui = adsk.core.Application.get().userInterface
            _ui.messageBox('Error in DocumentSavedHandler:\n{}'.format(traceback.format_exc()))



def run(context):
    """
    Called when the add-in is enabled. Hook event handlers and perform an initial safe sync
    only if a valid design is already active.
    """
    try:
        global _app, _ui
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        # Hook document events
        on_doc_activated = DocumentActivatedHandler()
        _app.documentActivated.add(on_doc_activated)
        _handlers.append(on_doc_activated)

        on_doc_saving = DocumentSavingHandler()
        _app.documentSaving.add(on_doc_saving)
        _handlers.append(on_doc_saving)

        on_doc_saved = DocumentSavedHandler()
        _app.documentSaved.add(on_doc_saved)
        _handlers.append(on_doc_saved)

        # Safe initial sync: only if there is an active design right now
        try:
            doc = _app.activeDocument
        except:
            doc = None

        if doc:
            des = get_active_design()
            if des and isinstance(des, adsk.fusion.Design):
                try:
                    sync_version_parameter()
                except:
                    _ui.messageBox('Initial sync error:\n{}'.format(traceback.format_exc()))

    except:
        if _ui:
            _ui.messageBox('Initialization error:\n{}'.format(traceback.format_exc()))


def stop(context):
    """
    Called when the add-in is disabled. Remove event handlers if possible and clear references.
    Fusion will usually clean up handlers, but removing them explicitly is safer.
    """
    try:
        global _handlers
        app = adsk.core.Application.get()
        if app:
            try:
                _handlers.clear()
            except:
                pass
    except:
        if _ui:
            _ui.messageBox('Stop error:\n{}'.format(traceback.format_exc()))
