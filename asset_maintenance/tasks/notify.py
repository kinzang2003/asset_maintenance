# tasks/notify.py
#
# WHAT THIS FILE IS:
# All the background/async work for this app lives here. Nothing in this file
# runs during a normal web request-response cycle — everything here is either:
#   (a) enqueued on-demand via frappe.enqueue() (see maintenance_request.py), or
#   (b) run automatically on a schedule (see scheduler_events in hooks.py).
#
# HOW REDIS FITS IN (this is the part the TOR specifically calls out):
# Frappe ships with three separate Redis instances configured in a bench:
#   - redis_cache    -> general caching (frappe.cache())
#   - redis_queue    -> the job queue used by frappe.enqueue() (python-rq under the hood)
#   - redis_socketio -> real-time websocket pub/sub (frappe.publish_realtime())
#
# When frappe.enqueue() is called, it doesn't run the function immediately.
# It serializes the function path + arguments into a job and LPUSHes it onto a
# Redis list. Separate `bench worker` processes are BLPOP-ing that same Redis
# list in a loop, 24/7, completely decoupled from the Gunicorn/web processes
# handling HTTP requests. This is why background jobs don't block user requests,
# and why they can keep retrying/running even if a web worker restarts.

import frappe
from frappe.utils import now_datetime, add_to_date


def notify_technician_assigned(request_name: str, technician: str, asset_name: str, priority: str):
	"""
	Enqueued by maintenance_request.py's on_request_submit() hook.

	In a real deployment this would call out to Slack's webhook API, send an
	SMTP email via frappe.sendmail(), or push to an SMS gateway. Those are all
	slow, network-bound I/O calls -- exactly the kind of work you never want
	blocking a user's "Submit" button click.

	Here we just log it (safe to run without any real credentials configured),
	but the pattern is identical to a production notification job.
	"""
	frappe.logger("asset_maintenance").info(
		f"[BACKGROUND JOB] Notifying {technician or 'UNASSIGNED'} — "
		f"new {priority} priority request {request_name} for asset '{asset_name}'"
	)

	# Example of what a REAL implementation would do (commented out so this
	# runs safely without mail server config):
	#
	# if technician:
	#     technician_doc = frappe.get_doc("Asset Technician", technician)
	#     frappe.sendmail(
	#         recipients=[technician_doc.contact_number],  # would be an email field in practice
	#         subject=f"New {priority} priority maintenance request: {request_name}",
	#         message=f"You've been assigned to fix: {asset_name}",
	#     )

	# publish_realtime pushes a live update over the Redis-backed websocket layer
	# to any open Frappe desk sessions -- e.g. to pop a toast notification without
	# the user refreshing the page.
	frappe.publish_realtime(
		event="maintenance_request_assigned",
		message={"request": request_name, "asset": asset_name, "priority": priority},
		user=frappe.session.user,
	)


def send_daily_open_requests_digest():
	"""
	Registered in hooks.py -> scheduler_events -> "daily".
	Frappe's scheduler (itself a background process reading a Redis-backed job
	schedule) calls this once every 24 hours automatically -- no cron entry
	needed on the OS level; `bench` manages that internally.
	"""
	open_requests = frappe.get_all(
		"Maintenance Request",
		filters={"status": ["in", ["Open", "In Progress"]]},
		fields=["name", "asset_name", "priority", "assigned_technician"],
		order_by="priority desc",
	)

	if not open_requests:
		frappe.logger("asset_maintenance").info("[DAILY DIGEST] No open requests today.")
		return

	summary_lines = [f"{r.name}: {r.asset_name} ({r.priority}) -> {r.assigned_technician or 'unassigned'}"
	                  for r in open_requests]
	frappe.logger("asset_maintenance").info(
		"[DAILY DIGEST] %d open request(s):\n%s" % (len(open_requests), "\n".join(summary_lines))
	)
	# Production version would email this digest to System Managers, e.g.:
	# frappe.sendmail(recipients=get_system_manager_emails(), subject="Daily Maintenance Digest", ...)


def check_overdue_requests():
	"""
	Registered in hooks.py -> scheduler_events -> "cron" -> "*/15 * * * *"
	(runs every 15 minutes). Demonstrates a more time-sensitive scheduled check --
	useful for SLA enforcement, which is a very real ERP/ops requirement.
	"""
	sla_cutoff = add_to_date(now_datetime(), hours=-24)

	overdue = frappe.get_all(
		"Maintenance Request",
		filters={
			"status": "Open",
			"priority": "Critical",
			"creation": ["<", sla_cutoff],
		},
		fields=["name", "asset_name", "creation"],
	)

	for req in overdue:
		frappe.logger("asset_maintenance").warning(
			f"[SLA BREACH] {req.name} ({req.asset_name}) has been open >24h and is still Critical priority."
		)
		# Could also auto-enqueue an escalation notification here via frappe.enqueue(...)
