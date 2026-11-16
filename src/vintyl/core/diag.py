"""
Diagnostic log and report, for bug reports and for telling us how Vintyl
works on a cutter.

The log (vintyl.log in Vintyl's settings folder, rotated at 1 MB with 3 old
files kept) records the start (versions, system), every job sent to a cutter
and how it ended, and uncaught errors with their traceback. The report puts
together the versions, the checks of --self-test, the chosen cutter, the
devices found, the user's groups and the end of the log, ready to paste into
an issue. Home folders are written as ~ (no user name in the report).

Adapted from Kerfly (kerfly/core/diag.py, commit cf48565).

Copyright (C) 2026 Kerfly contributors, Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import logging
import logging.handlers
import os
import platform
import sys
import threading
import traceback

log = logging.getLogger("vintyl")
log.addHandler(logging.NullHandler())        # quiet until setup()
LOG_NAME = "vintyl.log"
ISSUES_URL = "https://github.com/cyryllo/vintyl/issues/new"
ISSUE_TEMPLATES = {"bug": "bug_report.yml", "cutter": "cutter_report.yml"}
_handler = None


def config_dir():
    """Vintyl's own folder: next to VINTYL_SETTINGS (the tests), else ~/.config/vintyl."""
    if os.environ.get("VINTYL_SETTINGS"):
        return os.path.dirname(os.path.abspath(os.environ["VINTYL_SETTINGS"]))
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "vintyl")


def log_path():
    return os.path.join(config_dir(), LOG_NAME)


def setup(version=""):
    """Start logging to the file (and catch uncaught errors). Safe to call
    more than once; returns the log's path, or None when it cannot be written."""
    global _handler
    if _handler is not None:
        return log_path()
    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return None                                  # no log rather than no Vintyl
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False

    def excepthook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("Uncaught error:\n%s", text.rstrip())
        try:
            sys.__stderr__.write(text)
        except Exception:
            pass

    def thread_excepthook(args):
        log.error("Uncaught error in thread %s:\n%s", args.thread.name if args.thread else "?",
                  "".join(traceback.format_exception(args.exc_type, args.exc_value,
                                                     args.exc_traceback)).rstrip())

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
    log.info("==== Vintyl %s started: Python %s, %s", version, platform.python_version(), system_name())
    return path


def read_log(max_bytes=200_000):
    """The end of the log (the current file and the one before), oldest first."""
    path = log_path()
    parts = []
    for p in (path + ".1", path):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                parts.append(f.read())
        except OSError:
            pass
    return "".join(parts)[-max_bytes:]


def system_name():
    """Short name of the system, e.g. "Debian GNU/Linux 13 (trixie)"."""
    if platform.system() == "Linux":
        try:
            pretty = platform.freedesktop_os_release().get("PRETTY_NAME")
            if pretty:
                return pretty
        except (OSError, AttributeError):
            pass
    return platform.platform()


def _private(text):
    """Home folders as ~, so the report carries no user name."""
    home = os.path.expanduser("~")
    return text.replace(home, "~") if home and home != "/" else text


CUTTER_GROUPS = ("lp", "dialout", "uucp", "tty", "plugdev")


def user_groups():
    """Which of the groups that decide access to cutters this session has:
    {"lp": True, "dialout": False, ...} (only those, so the report never
    carries the user's own group, which has their name)."""
    try:
        import grp
        have = set()
        for g in os.getgroups():
            try:
                have.add(grp.getgrgid(g).gr_name)
            except KeyError:
                pass
    except (ImportError, OSError):
        return {}
    return {name: name in have for name in CUTTER_GROUPS}


def build_report(version, checks=(), cutter=None, settings=None, extra=()):
    """Text of a diagnostic report. checks: (OK/FAIL, name, detail) lines;
    cutter: the chosen profile; settings: {key: value}; extra: more lines."""
    from . import transport
    lines = ["Vintyl diagnostic report", "Vintyl %s" % version,
             "Python %s (%s)" % (platform.python_version(), platform.architecture()[0]),
             "System %s" % system_name(),
             "Session %s, display %s" % (os.environ.get("XDG_SESSION_TYPE", "?"),
                                         os.environ.get("QT_QPA_PLATFORM") or os.environ.get("WAYLAND_DISPLAY")
                                         and "wayland" or os.environ.get("DISPLAY") and "x11" or "?"),
             "AppImage %s" % ("yes" if os.environ.get("APPIMAGE") else "no")]
    lines += list(extra)
    lines.append("")
    if checks:
        lines.append("== Checks")
        lines += ["%-4s  %-22s %s" % tuple(c) for c in checks]
        lines.append("")
    lines.append("== Cutter")
    if cutter is not None:
        p = cutter
        lines += ["%s: %s, port %s, %s, %.1f mm wide, %g units/mm" % (p.name, p.connection, p.port or "-",
                                                                    p.language.upper(), p.width_mm,
                                                                    p.units_per_mm),
                  "knife offset %.2f mm, overcut %.2f mm, speed and force sent: %s, sending: %s"
                  % (p.knife_offset_mm, p.overcut_mm, "yes" if p.send_speed_force else "no", p.pacing)]
        if p.port:
            exists = os.path.exists(p.port)
            problem = transport.access_problem(p.port)
            lines.append("port %s: %s" % (p.port, "not there" if not exists else
                                          ("no access: " + problem.splitlines()[0]) if problem else "usable"))
    lines.append("devices found: %s" % (", ".join(transport.find_ports()) or "none"))
    groups = user_groups()
    lines.append("groups: %s" % (", ".join("%s %s" % (n, "yes" if on else "no") for n, on in groups.items()) or "?"))
    lines.append("")
    if settings:
        lines.append("== Settings")
        lines += ["%s = %s" % (k, settings[k]) for k in sorted(settings)]
        lines.append("")
    lines += ["== Log (%s)" % log_path(), read_log() or "(empty)"]
    return _private("\n".join(lines))


def issue_url(kind, version, cutter=""):
    """The GitHub issue form ("bug" or "cutter") with the version, the system
    and the cutter filled in (the form fields have these ids)."""
    from urllib.parse import urlencode
    fields = {"template": ISSUE_TEMPLATES[kind], "version": version, "system": system_name()}
    if cutter:
        fields["cutter"] = cutter
    return ISSUES_URL + "?" + urlencode(fields)
