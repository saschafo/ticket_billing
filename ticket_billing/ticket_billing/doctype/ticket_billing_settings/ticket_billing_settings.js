// Verwaltung der Demo-Daten.
//
// Nur für Administratoren sichtbar, und das Entfernen fragt nach. Der Grund
// steht in der Warnung selbst: Solange Demo-Daten installiert sind, kommt
// jeder ohne Passwort in die Anwendung.

frappe.ui.form.on('Ticket Billing Settings', {
	refresh(frm) {
		if (!frappe.user.has_role('System Manager')) return

		frappe.call({
			method: 'ticket_billing.demo.get_demo_status',
			callback: ({ message }) => {
				const installed = message && message.installed
				render_status(frm, installed)

				// Beides kann gleichzeitig sinnvoll sein: Nach dem
				// Entfernen bleibt liegen, woran echte Daten haengen.
				// Dann ist nichts mehr zu entfernen, was ginge, aber die
				// Installation ist auch nicht vollstaendig.
				if (installed) {
					frm.add_custom_button(
						__('Remove demo data'),
						() => confirm_remove(frm),
						__('Demo data'),
					)
				}

				if (!message || !message.complete) {
					frm.add_custom_button(
						__('Install demo data'),
						() => install(frm),
						__('Demo data'),
					)
				}
			},
		})
	},
})

function render_status(frm, installed) {
	if (!installed) {
		frm.dashboard.clear_headline()
		return
	}

	frm.dashboard.set_headline(
		__(
			'Demo data is installed. The login page offers one-click sign-in for the demo users, and the hourly rates on the activity types are placeholders (Ticket-Support 75 €/h, Beratung 120 €/h) — do not leave this enabled on a system with real data.',
		),
		'orange',
	)
}

function install(frm) {
	frappe.confirm(
		__(
			'Create demo users, departments, tickets and time entries? The demo users share a known password.',
		),
		() => {
			frappe.dom.freeze(__('Creating demo data …'))
			frappe
				.call({ method: 'ticket_billing.demo.install_demo_data' })
				.then(({ message }) => {
					frappe.dom.unfreeze()
					frappe.msgprint({
						title: __('Demo data installed'),
						indicator: 'green',
						message: __('{0} records created, including {1} tickets.', [
							message.records,
							message.tickets,
						]),
					})
					frm.reload_doc()
				})
				.catch(() => frappe.dom.unfreeze())
		},
	)
}

function confirm_remove(frm) {
	// Zweistufig: Erst die Warnung, dann das Tippen des Wortes. Löschen ist
	// nicht rückgängig zu machen, und der Knopf sitzt neben harmlosen.
	const dialog = new frappe.ui.Dialog({
		title: __('Remove demo data'),
		fields: [
			{
				fieldtype: 'HTML',
				options: `<p>${__(
					'Only records created by the demo installation are deleted — real data entered later is not affected.',
				)}</p>`,
			},
			{
				fieldtype: 'Data',
				fieldname: 'confirm',
				label: __('Type REMOVE to confirm'),
				reqd: 1,
			},
		],
		primary_action_label: __('Remove'),
		primary_action({ confirm }) {
			if ((confirm || '').trim().toUpperCase() !== 'REMOVE') {
				frappe.msgprint(__('Please type REMOVE to confirm.'))
				return
			}

			dialog.hide()
			frappe.dom.freeze(__('Removing demo data …'))
			frappe
				.call({ method: 'ticket_billing.demo.remove_demo_data' })
				.then(({ message }) => {
					frappe.dom.unfreeze()
					const failed = (message.failed || []).length
					frappe.msgprint({
						title: __('Demo data removed'),
						indicator: failed ? 'orange' : 'green',
						message: failed
							? __('{0} records removed, {1} could not be deleted.', [
									message.removed,
									failed,
								])
							: __('{0} records removed.', [message.removed]),
					})
					frm.reload_doc()
				})
				.catch(() => frappe.dom.unfreeze())
		},
	})

	dialog.show()
}
