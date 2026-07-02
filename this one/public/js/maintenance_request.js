// maintenance_request.js
//
// WHAT THIS FILE IS:
// Client-side scripting for the Maintenance Request DOCTYPE FORM (desk UI), wired
// up via doctype_js in hooks.py. This runs in the browser, not on the server --
// it's for instant UI feedback (button visibility, computed fields, warnings)
// BEFORE a save round-trip to the server. This is the "client-side scripting"
// bullet from the TOR, paired with maintenance_request.py's server-side half.
//
// IMPORTANT PRINCIPLE: never trust client-side JS alone for business rules.
// Everything meaningful enforced here (e.g. cost sanity) is ALSO enforced in
// maintenance_request.py's validate(), because a user could bypass this JS
// entirely by calling the REST API directly. Client JS is for UX, server code
// is for correctness.

frappe.ui.form.on("Maintenance Request", {
	// refresh runs every time the form (re)loads or after a save.
	refresh(frm) {
		// Custom button, only shown once the doc has been submitted and isn't
		// resolved/closed yet -- a clean example of conditional UI logic.
		if (frm.doc.docstatus === 1 && !["Resolved", "Closed"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Mark Resolved"), () => {
				mark_resolved_dialog(frm);
			});
		}

		// Visual nudge: highlight the priority field red if Critical, so techs
		// scanning a list of open forms don't have to read the label carefully.
		if (frm.doc.priority === "Critical") {
			frm.set_intro(__("Critical priority — please assign a technician immediately."), "red");
		}
	},

	// Fires specifically when the user changes the asset_tag field -- this is a
	// "field trigger", the most common client script pattern in Frappe.
	asset_tag(frm) {
		if (frm.doc.asset_tag) {
			const tag = frm.doc.asset_tag.toUpperCase();
			if (tag.includes("SRV") || tag.includes("RACK")) {
				// Mirrors the server-side auto-escalation logic in
				// _auto_set_priority_for_critical_assets(), but applied instantly
				// client-side so the user sees it change before they even save.
				frm.set_value("priority", "High");
				frappe.show_alert({
					message: __("Priority auto-escalated to High: server/rack asset detected."),
					indicator: "orange",
				});
			}
		}
	},

	// Live client-side validation echoing the server rule, so the user gets
	// instant feedback instead of waiting for a round trip that will just fail.
	actual_cost(frm) {
		validate_cost_variance_client_side(frm);
	},
	estimated_cost(frm) {
		validate_cost_variance_client_side(frm);
	},
});

function validate_cost_variance_client_side(frm) {
	const { actual_cost, estimated_cost } = frm.doc;
	if (actual_cost && estimated_cost && actual_cost > estimated_cost * 2) {
		frm.set_df_property(
			"resolution_notes", "reqd", 1
		);
		frappe.show_alert({
			message: __("Actual cost is more than double the estimate — resolution notes will be required."),
			indicator: "orange",
		});
	} else {
		frm.set_df_property("resolution_notes", "reqd", 0);
	}
}

function mark_resolved_dialog(frm) {
	// frappe.prompt is a quick way to collect a couple of fields in a modal
	// without building a full custom Dialog -- good for simple action buttons.
	frappe.prompt(
		[
			{ fieldname: "resolution_notes", label: __("Resolution Notes"), fieldtype: "Small Text", reqd: 1 },
			{ fieldname: "actual_cost", label: __("Actual Cost (Nu.)"), fieldtype: "Currency" },
		],
		(values) => {
			// Calls our custom whitelisted API method directly from the client --
			// this is the same endpoint an external system could call over plain
			// HTTP (see api/maintenance_api.py -> mark_resolved).
			frappe.call({
				method: "asset_maintenance.api.maintenance_api.mark_resolved",
				args: {
					request_id: frm.doc.name,
					resolution_notes: values.resolution_notes,
					actual_cost: values.actual_cost || 0,
				},
				callback: () => {
					frappe.show_alert({ message: __("Request marked resolved."), indicator: "green" });
					frm.reload_doc();
				},
			});
		},
		__("Resolve Maintenance Request"),
		__("Submit")
	);
}
