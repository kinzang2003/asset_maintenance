# hooks.py
#
# WHAT THIS FILE IS:
# Every Frappe app has exactly one hooks.py. Frappe reads this file at startup to learn
# how your app plugs into the framework — what DocType events to listen for, what
# background jobs to schedule, what JS to inject into forms, etc.
#
# Think of it as the "wiring diagram" for the app. None of the logic lives here —
# it just points to functions defined elsewhere.

from . import __version__ as app_version  # noqa: F401

app_name = "asset_maintenance"
app_title = "Asset Maintenance"
app_publisher = "Kinzang Dorji"
app_description = "Custom Frappe/ERPNext app for tracking asset maintenance requests"
app_email = "kinzasdorji66@gmail.com"
app_license = "MIT"

# ---------------------------------------------------------------------------
# DOC EVENTS
# ---------------------------------------------------------------------------
# This is one of the most important hooks in Frappe. It lets you attach Python
# functions to lifecycle events of ANY DocType (including core ones you didn't
# write) without editing their source code.
#
# Format:
#   doc_events = {
#       "DocType Name": {
#           "event_name": "python.module.path.function"
#       }
#   }
#
# Here, whenever a Maintenance Request is submitted (docstatus goes to 1),
# Frappe will call our function to kick off a background job.
doc_events = {
    "Maintenance Request": {
        "on_submit": "asset_maintenance.asset_maintenance.doctype.maintenance_request.maintenance_request.on_request_submit",
        "validate": "asset_maintenance.asset_maintenance.doctype.maintenance_request.maintenance_request.validate_request",
    }
}
# NOTE ON THE DOTTED PATH ABOVE:
# Real path on disk: asset_maintenance/asset_maintenance/asset_maintenance/doctype/maintenance_request/maintenance_request.py
# Import path drops the outermost folder (that's the app's install root, not part
# of the Python package) -> asset_maintenance.asset_maintenance.doctype.maintenance_request.maintenance_request
# This "app repeats its own name twice" pattern trips up almost everyone the first
# time they build a Frappe app -- it's a known quirk of bench's scaffolding.

# ---------------------------------------------------------------------------
# SCHEDULED TASKS (this is how Frappe uses Redis + background workers)
# ---------------------------------------------------------------------------
# Frappe's scheduler (bench's `worker` + `scheduler` processes) uses Redis as the
# queue broker. Any function listed here gets run automatically by a background
# worker process, completely separate from the web request/response cycle.
#
# This means: a user submitting a form never has to "wait" for this to run.
scheduler_events = {
    "daily": [
        "asset_maintenance.tasks.notify.send_daily_open_requests_digest",
    ],
    "cron": {
        # Runs every 15 minutes — good for near-real-time SLA checks
        "*/15 * * * *": [
            "asset_maintenance.tasks.notify.check_overdue_requests",
        ]
    },
}

# ---------------------------------------------------------------------------
# CLIENT-SIDE ASSETS
# ---------------------------------------------------------------------------
# Injects our custom JS into the Maintenance Request form. This is how you add
# client-side scripting (button handlers, dynamic field visibility, etc.)
doctype_js = {"Maintenance Request": "public/js/maintenance_request.js"}

# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
# Fixtures let you ship default/seed data (like Workflow definitions or Roles)
# as part of the app itself, so `bench migrate` recreates them on any new site.
fixtures = [
    {"dt": "Workflow", "filters": [["name", "=", "Maintenance Request Workflow"]]},
]
