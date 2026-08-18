# Ticket Billing

*[Deutsch](README.md) · English*

Frappe app for ticket handling and billing, built on **ERPNext 16** and
**Frappe Framework 16**.

Tickets arrive as e-mail from external customers or as internal requests
between departments. Access is separated by department and role, new tickets
are assigned automatically, and recorded time passes a two-person review
before it reaches ERPNext invoicing.

The matching Docker setup lives in its own repository:
[`ticket_billing_docker`](https://github.com/saschafo/ticket_billing_docker).

---

## Contents

* [Data model](#data-model)
* [Roles and permissions](#roles-and-permissions)
* [Automatic assignment](#automatic-assignment)
* [E-mail](#e-mail)
* [Time tracking](#time-tracking)
* [Two-person review](#two-person-review)
* [Realtime](#realtime)
* [User interface](#user-interface)
* [Localisation](#localisation)
* [Metrics](#metrics)
* [Billing](#billing)
* [Demo data](#demo-data)
* [Security notes](#security-notes)
* [Boundaries of the design](#boundaries-of-the-design)
* [Setup that belongs to the installation](#setup-that-belongs-to-the-installation)
* [Licence](#licence)

---

## Data model

No custom ticket doctypes — the app extends ERPNext:

| Doctype | Field | Purpose |
|---|---|---|
| `Issue` | `tb_department` | responsible department (mandatory) |
| `Issue` | `tb_origin` | `Internal` / `External` |
| `Issue` | `tb_assigned_employee` | assigned employee |
| `Issue` | `tb_first_response_on` | timestamp of first response |
| `Issue` | `tb_resolved_on` | timestamp of resolution |
| `Issue` | `customer` (ERPNext) | only allowed for external origin |
| `Timesheet Detail` | `tb_issue` | links the time entry to the ticket |
| `Email Account` | `tb_department` | one mailbox per department |

Own doctypes: `Ticket Billing Settings`, `Ticket Timer` (a single running
timer) and `Ticket Billing Demo Record` (demo data tracking).

[`setup.py`](ticket_billing/setup.py) creates the fields idempotently on
`after_install` and on every `after_migrate` — deliberately not as fixtures.
Fixtures on foreign doctypes break as soon as ERPNext changes something there.

## Roles and permissions

| Role | Scope |
|---|---|
| `Mitarbeiter` (agent) | tickets assigned to them, plus tickets they created |
| `Abteilungsleiter` (lead) | all tickets of their department, reassignment, team stats, time approval |
| `Geschäftsführung` (management) | **read-only** across departments |

Enforced on three layers, all server-side:

1. **DocPerms** as the ceiling (what a role may do at all).
2. **User Permission on `Department`** — mirrored from `Employee.department`
   ([`doc_events/employee.py`](ticket_billing/doc_events/employee.py)) and
   applied by Frappe to every query.
3. **`permission_query_conditions` and `has_permission`**
   ([`permissions.py`](ticket_billing/permissions.py)) for row-level
   restriction. This covers Desk, reports, `frappe.get_list` **and** REST —
   not just the UI.

Every whitelisted endpoint checks again itself. The metric endpoints
deliberately bypass the row filters (a figure has to count what you may not
see individually), which is why each of them starts with an explicit check.

> **Important:** `tb_assigned_employee` carries `ignore_user_permissions`.
> ERPNext creates a self-referencing User Permission for every Employee;
> without this flag a lead would only see tickets assigned to themselves.

## Automatic assignment

`after_insert` fires for every new ticket, including those created from
incoming mail. The rule is pluggable:

```
assignment/
├── base.py                    interface (Candidate, AssignmentStrategy)
├── registry.py                registry, @register
├── strategies/
│   ├── __init__.py            imports the rules
│   └── by_workload.py         default rule: fewest open tickets
└── __init__.py                frame: candidates → rule → apply
```

A new rule (round robin, category based, manual confirmation):

```python
# assignment/strategies/round_robin.py
from ticket_billing.assignment.base import AssignmentStrategy
from ticket_billing.assignment.registry import register

@register
class RoundRobinStrategy(AssignmentStrategy):
    key = "round_robin"
    label = "Round robin"

    def select(self, issue, candidates):
        ...  # None means: leave unassigned, the lead decides
```

Add one import line to `strategies/__init__.py` and set
`assignment_strategy` to `round_robin` in the settings. Nothing else changes.

Assignment errors are logged, not raised: an unassigned ticket is visible and
can be distributed later, an e-mail lost to a mandatory field is not.

System senders (`mailer-daemon@`, `postmaster@`, `noreply@` …) are skipped —
a bounce is not work for anyone.

---

## E-mail

The full round trip: mail to a department mailbox becomes a ticket, the agent
replies from within the ticket, and the customer's answer attaches to the
same case.

### Inbound: the mailbox decides the department

One `Email Account` per department carrying `tb_department`. For IMAP,
`append_to = Issue` must be set on the **folder** row (`IMAP Folder`), not on
the account — with IMAP enabled Frappe only reads the folder row.

The department is resolved in this order
([`doc_events/issue.py`](ticket_billing/doc_events/issue.py)):

1. **department of the receiving mailbox** — takes precedence even if the
   field already holds a value,
2. what is set on the ticket (when created in the UI),
3. the default department from the settings,
4. otherwise a clear error.

> **Why the mailbox wins:** Frappe pre-fills link fields from user
> permissions. Someone allowed to see exactly one department gets it written
> into new documents automatically. If an agent fetches the mail, the ticket
> would be created in **their** department instead of the mailbox's — mail to
> accounting would land in support. A pre-filled value is not a decision.

For the mailbox to reach the ticket at all, the app sets the property setter
`Issue.recipient_account_field = email_account` (see below).

### Origin: internal or external

`tb_origin` decides more than a label: time on **external** tickets is billable
and flows into invoicing, internal time is not.

A sender counts as internal if any of these hold:

* the address is one of our own mailboxes,
* it belongs to an **active employee** (`Employee.user_id`),
* it is on the same domain as one of our mailboxes.

Deliberately `Employee` and not `User`: a customer with portal access is a
user too, but not part of the company.

> The domain rule assumes nobody outside writes from your own domains. If you
> have customers on a domain of yours, this needs a different approach.

### Conversation and replies

The body of an incoming mail is **not** stored in `Issue.description` but in
linked `Communication` records. The detail view shows them under the
*Conversation* tab with sender, timestamp and attachments — rendered as text,
not HTML (foreign mail is never rendered unchecked).

Replying works directly from the ticket: recipients are pre-filled (sender of
the last inbound message, otherwise the original sender), the sender is the
department mailbox. The reply carries `in_reply_to`, so the customer's answer
returns to the **same ticket**. Status moves to *Replied*.

**Replies are sent immediately.** Otherwise Frappe only queues outgoing mail
and the scheduler drains that queue every four minutes — measured 11 to 244
seconds. The endpoint triggers the matching queue entries directly, as a
background job (the SMTP round trip must not stall the UI). If that fails,
the regular batch picks them up; no mail is lost.

In the ticket list a row is marked **New reply** as soon as the most recent
message came from outside — but only for a message *after* the opening one.
Otherwise every new ticket would carry it, and a marker everyone carries says
nothing.

### Bounces

A delivery failure returns as mail from the mail system. Left alone, Frappe
creates a separate ticket for it and assignment pushes it into someone's
queue — a system notice looking like a customer request.

[`mail_filter.py`](ticket_billing/mail_filter.py) recognises system senders by
the local part and attaches the message to the ticket whose reply bounced.
The ticket name comes from the unsubscribe link inside the quoted original,
i.e. a system-generated anchor. In addition the requester's address must
appear in the bounce — otherwise the failed mail went to someone else (an
internal notification, say) and does not belong in the customer conversation.
If nothing can be resolved, the ticket is closed rather than deleted.

### Fetching

The scheduler polls every ten minutes (`0/10 * * * *`), measured 74 to 482
seconds until arrival. **Fetch mail** in the list views does it on demand: one
poll takes about 0.25 seconds per mailbox and reports immediately what came in.

A **shared** ten-second lock throttles it — not one per user: the load is on
the mail server, and simultaneous clicks must not multiply connections. The
permission check sits in the endpoint; a hidden button is not a barrier.

### Requirements for outgoing mail

Large providers reject mail when the sending domain cannot authenticate.
Since 2024 Gmail requires **SPF or DKIM**:

```
550-5.7.26 Your email has been blocked because the sender is unauthenticated.
550-5.7.26 Gmail requires all senders to authenticate with either SPF or DKIM.
```

The sending domain's DNS therefore needs:

| Record | Example |
|---|---|
| `A` | the mail server's IP |
| `TXT` (SPF) | `v=spf1 a:mail.example.org include:… ~all` |
| `TXT` `default._domainkey` | the server's DKIM key |
| `TXT` `_dmarc` | `v=DMARC1; p=none; rua=mailto:postmaster@example.org` |

SPF must name the server that **actually sends**. A record still pointing at a
previous mail provider is the most common cause of rejection.

---

## Time tracking

Start/stop a timer or enter a duration manually. Both create a row in an
ERPNext timesheet, linked to ticket, employee and — for external tickets —
the customer. The timer lives on the server, so it survives reloads and
device changes.

**One timer per employee.** Guaranteed by a unique index on
`Ticket Timer.employee`. The controller check only produces the readable
message — two near-simultaneous requests would slip past it, not past the
index.

**Stopping asks first.** The dialog shows the measured duration, editable
(`1:30` or `1.5`), with *Discard* next to it. A shortened duration is anchored
at the timer's start, not counted backwards from now: ERPNext rejects
overlapping time entries for the same employee, and counting backwards would
regularly run into a previously booked entry. Bounds: at least one minute, at
most 24 hours per entry.

**Warning threshold**: if a timer runs longer than `timer_warning_hours`
(default 4, configurable), the header and detail view change colour.

The elapsed time counts up in the browser without polling. It is computed from
the duration the server reported on the last call plus elapsed browser time —
not from `start_time`: Frappe returns that timestamp without a zone, the
browser reads it as local time, and with a differing zone the display would be
off by exactly that difference.

**One timesheet per entry.** ERPNext submits per *document* — only that way can
a single entry be edited, deleted and approved independently.

## Two-person review

Recorded time starts as a **draft** (`docstatus` 0). Only the department lead
submits it.

| | Agent | Lead |
|---|---|---|
| edit/delete own drafts | yes | — |
| others' drafts in own department | no | edit and submit |
| other departments | no | no |
| submitted entries | read only | read only |

Submitted means immutable — Frappe handles that itself (changes after
submission are rejected, deletion requires cancellation first). A separate
locking mechanism would only add a second place where things can go wrong.

Routes: `/ticketbilling/zeiten` (own entries, status *Draft* / *Submitted*)
and `/ticketbilling/zeiten-buchen` (approval, multi-select, period filter).
Bulk submission wraps every entry in its own savepoint: one rejected document
does not take the others down, and failures are reported per entry.

**Daily reminder**: a scheduler job notifies leads about drafts older than
`draft_reminder_days` (default 3) — as a Frappe notification, without e-mail,
in each recipient's own language.

### Four deviations from ERPNext default behaviour

All set by [`setup.py`](ticket_billing/setup.py), all reversible:

* **Overlap validation off**
  (`Projects Settings.ignore_employee_time_overlap`). ERPNext rejects time
  entries of the same employee with overlapping periods. Here a *duration* is
  recorded; the clock times are only a frame. An hour added next to a running
  timer would otherwise not be bookable.
* **`Timesheet.employee` ignores user permissions** (property setter).
  ERPNext creates a self-referencing User Permission per employee; without
  this exception a lead could not reach their team's entries. Who sees what is
  still decided by `permissions.py`.
* **`Issue.recipient_account_field = email_account`** (property setter).
  Frappe writes the receiving mailbox into whichever field this property
  names. ERPNext does not set it — `email_account` would stay empty and the
  department could not be derived from the mailbox.
* **Default activity type** (`Activity Type`, default `Ticket-Support`).
  ERPNext requires an activity type on *submission*; without it approval, not
  recording, would fail.

## Realtime

The UI does not wait for a click on *Refresh*.

| Event | When | Recipients |
|---|---|---|
| `ticket_billing:ticket` | assignment, status/subject/priority change, **incoming reply** | assignee, previous assignee, creator, department leads |
| `ticket_billing:timer` | timer started, submitted or discarded | the user's own other sessions |

Messages go exclusively into **user rooms**, and the server decides the
recipient list ([`realtime.py`](ticket_billing/realtime.py)). A room the client
subscribes to itself would only be as tight as the room management — this way
nobody can be delivered anything they may not already see. The payload
therefore only contains what the list shows anyway.

The event is only a trigger: data is reloaded through the normal,
permission-checked endpoints, debounced by 400 ms — a reassignment produces
events for several people at once.

> **Prerequisite:** nginx must pass the real `Origin` to the socket service.
> Frappe compares it against `Host`; the original `frappe_docker` template
> pins it to the site name, which makes every connection via `localhost:8080`
> fail. The Docker repo adjusts this.

> **Second prerequisite:** the app must be opened under the **site name**, not
> via `localhost`. The socket service validates the session by calling back to
> the backend and builds that address from the browser's `Origin`. Inside the
> container `localhost` points at the container itself — the call fails. The
> Docker setup provides a network alias on the `frontend` service for this.

## User interface

![My tickets](docs/screenshots/01-meine-tickets.png)

Vue 3 + Vite under `ticket_billing/frontend`, built into
`ticket_billing/public/frontend` (committed — the Docker build needs no Node
step).

| Route | Area | Role |
|---|---|---|
| `/ticketbilling/tickets` | own tickets, time tracking | agent |
| `/ticketbilling/zeiten` | own time entries | agent |
| `/ticketbilling/abteilung` | department tickets, reassignment, team stats | lead |
| `/ticketbilling/abteilung/kennzahlen` | metrics for the own department | lead |
| `/ticketbilling/zeiten-buchen` | time approval | lead |
| `/ticketbilling/auswertung` | cross-department metrics | management |

The router only hides what would return no data anyway — enforcement lives in
the backend.

**Handling.** The header carries the language switch, a toggle between
centred (max 1280 px) and full width (remembered in `localStorage`), the
running timer and sign-out. Ticket details are split into two tabs — *Case*
(master data, time tracking, editing, reassignment) and *Conversation*
(e-mails, replies). Without that split a long mail thread pushed time tracking
out of view. If the requester wrote last, the view opens on the conversation.

Icons: [`@tabler/icons-vue`](https://tabler.io/icons), used sparingly and at a
consistent size.

```bash
cd ticket_billing/frontend
npm install
npm run build          # lints with ESLint, then builds
npm run lint           # lint only
npm run dev            # http://localhost:8083 against a running bench
```

> **ESLint runs before every build**, deliberately with error rules only and
> no formatting — a red run should always mean something. The trigger was a
> `computed()` without an import: the build compiles it happily, the component
> throws only in the browser, and a component that throws while mounting
> renders **silently nothing**. The `no-undef` rule catches exactly that.

### Views

| | |
|---|---|
| ![Department](docs/screenshots/03-abteilung.png) | ![Department metrics](docs/screenshots/04-abteilung-kennzahlen.png) |
| **Department** — all cases, workload per employee, split by status and origin | **Department metrics** — trend per employee, workload, origin, unsubmitted time |
| ![My time entries](docs/screenshots/02-meine-zeiten.png) | ![Time approval](docs/screenshots/05-zeiten-buchen.png) |
| **My time entries** — own records, drafts editable | **Time approval** — release by the lead, multi-select |
| ![Metrics](docs/screenshots/06-auswertung.png) | ![Sign-in](docs/screenshots/07-anmeldung.png) |
| **Metrics** — across departments, read-only | **Sign-in** — quick logins only while demo data is installed |

The images are produced by [`docs/screenshots.sh`](docs/screenshots.sh) using
the headless Chromium that ships inside the Frappe image — captured with demo
users, never with real data. After UI changes they can be regenerated in one
go, so they do not quietly go stale.

## Localisation

**Frontend** (`frontend/src/i18n/`): vue-i18n, German and English complete. A
new language means a file under `locales/`, an import and an entry in
`AVAILABLE_LOCALES`.

**Server**: all user-facing text through `frappe._()`, sources in English,
translations in [`translations/de.csv`](ticket_billing/translations/de.csv).
Labels of own doctypes and custom fields are English as well, so a new
language needs no code change.

The language switch acts on three levels: vue-i18n for display, localStorage
for the next visit, and `User.language` — so server-side messages, e-mails and
PDFs follow the choice too.

## Metrics

### Management

`/ticketbilling/auswertung`, period 7 / 30 / 90 / 365 days. Read-only — the
role has no server-side write permission on `Issue`.

* Volume over time, stacked by department. Empty days or weeks are filled in:
  without that the axis would only show points that had tickets, and a quiet
  week would look like two consecutive days.
* Average response time (creation → first status change) and average
  resolution time (creation → resolved) per department. The overall average is
  **weighted** by ticket count — otherwise a department with two cases would
  count as much as one with two hundred.
* Internal/external share per department, as percentages rather than absolute
  numbers.
* Hours per department, split into billable (external ticket) and internal,
  plus submitted versus draft.
* Workload per employee: open tickets and hours recorded in the period.

**Excel export** via `export_management_kpis` — three sheets (departments,
employees, trend), headers in the caller's language. Produced with openpyxl,
which Frappe ships anyway.

### Department leads

`/ticketbilling/abteilung/kennzahlen` — the same metric groups limited to the
own department: four tiles, a twelve-week trend per employee, workload as
bars, origin as a donut. Plus a tile for unsubmitted time with a jump into the
approval view.

The time metrics build on the app's own timestamps `tb_first_response_on` and
`tb_resolved_on` — ERPNext's `first_responded_on` and `sla_resolution_date`
stay empty without a configured service level agreement.

## Billing

Invoicing runs **deliberately through the standard ERPNext desk**, not through
the Vue app. The app only reports billable hours as a metric and creates no
invoices.

For *Timesheet → Sales Invoice* to work in the desk without extra steps, the
app sets:

| Field | Source |
|---|---|
| `Timesheet.customer` | customer of the ticket, external origin only |
| `Timesheet Detail.is_billable` | 1 when the ticket has a customer |
| `Timesheet Detail.activity_type` | default activity type from the settings |

`is_billable` is the decisive one: ERPNext only sums such rows into
`total_billable_hours`, and *Sales Invoice from Timesheet* aborts at zero
billable hours.

**The hourly rate belongs to the activity type**, not the employee. On
submission ERPNext first looks for an `Activity Cost` for the employee/activity
combination and only then falls back to the rates on the `Activity Type` — an
`Activity Cost` without an employee would never be found. The rates therefore
belong on the activity type.

Without demo data they are **0**: an hourly rate is a pricing decision and does
not belong in an installation routine. Invoices then come out at zero —
visibly wrong instead of quietly wrong.

Standard ERPNext prerequisite: a **fiscal year** must exist. Without it no
invoice can be booked.

## Demo data

**For demonstration and testing only.** Ticket Billing Settings (Desk, System
Manager only) offers *Install demo data* and *Remove demo data*.

Created are two departments, five users with roles and employee records, three
customers and tickets spread over **13 weeks** — 2 to 8 per employee and week,
unevenly distributed so the charts look meaningful (around 225 tickets). Plus
time entries as drafts and submitted, and the billing basics:

| | **Placeholder values** |
|---|---|
| Activity type `Ticket-Support` | 75 €/h billing, 45 €/h costing |
| Activity type `Beratung` | 120 €/h billing, 70 €/h costing |
| Item `Support-Stunde` | service, unit hour |

On removal the rates are reset to 0 — a demo rate must never end up on a real
invoice. Tickets are created through the normal path so the assignment rule
applies; date and status are backdated afterwards.

Demo users receive **no e-mail** (`thread_notify = 0`). Their addresses end in
`@demo.local` and do not exist; every notification would come back as a bounce
and have to be sorted out again.

Every created record is noted in `Ticket Billing Demo Record`, and **only what
is listed there** is deleted on removal — in reverse creation order so no
references break. Matching by name or subject would be dangerous: a real
ticket with the same subject would disappear with it.

**Whatever real data depends on stays.** An employee referenced by a real
ticket, a customer with an invoice, a demo ticket with submitted time — they
are reported, not deleted. Whether a complete installation exists is therefore
decided by an explicit marker that removal always clears: otherwise those
leftovers would count as "installed" and you could never return to a clean
state — removal would clear nothing more, installation would refuse to run.

While demo data is installed, the login page offers one-click sign-in for the
demo users. Sign-in goes through a dedicated endpoint that verifies demo data
is installed **and** that the user comes from the tracking table — a real
account cannot be taken over this way. No password ever appears in the
frontend.

## Security notes

> **Demo data does not belong on a system holding real data.** Anyone who
> knows the address gets in without a password. The settings page says so, and
> removal requires typing `REMOVE`.

* **Ticket descriptions and mail bodies are rendered as text**, not HTML —
  they come from foreign e-mail. Formatted display would require server-side
  sanitising against an allow-list first.
* **Every endpoint checks for itself.** A hidden button is not a barrier; the
  UI only hides what would return no data anyway.
* **Realtime only sends into user rooms** whose recipients the server decides.
* **`frappe.set_user()` does not belong inside a web request.** It overwrites
  `session.sid` and clears the session data — the caller's login becomes
  invalid, and the failure only shows on the next request.
* **The site URL must be configured** (`host_name`), otherwise unsubscribe and
  attachment links in outgoing mail point nowhere.

## Boundaries of the design

Not defects but decisions — with the reasoning behind them:

* **An employee belongs to exactly one department**
  (`Employee.department`). Multiple memberships would have turned the
  permission check from one department into a set, in all three places. For
  someone helping out a second department, reassignment by the lead is the
  simpler route.
* **Invoicing has no dedicated UI.** It runs through the ERPNext desk, see
  [Billing](#billing). A second interface for invoices would be a second place
  where amounts can come into existence.
* **A bounce that cannot be attributed is closed, not deleted.** Automatically
  deleting what was not identified with certainty is the more dangerous path —
  a closed ticket appears in no work list and can still be inspected.

## Setup that belongs to the installation

None of this is set by the app — these are operator decisions:

* **`email_sync_option` on the `Email Account`** defaults to `UNSEEN` in
  Frappe. Anything opened in webmail is then no longer fetched. `ALL` is more
  robust but causes more load. If the mailboxes are only used through the app,
  `UNSEEN` is fine.
* **`host_name`** must be set, otherwise links in outgoing mail point nowhere.
* **SPF and DKIM** for the sending domain, see
  [Requirements for outgoing mail](#requirements-for-outgoing-mail).
* **A fiscal year** in standard ERPNext, otherwise no invoice can be booked.

## Licence

[GNU Affero General Public License v3.0](license.txt)

Copyright (C) 2026 Sascha Böhm Software & App, Inhaber Sascha Böhm

AGPL rather than a permissive licence because the app runs exclusively with
ERPNext (GPL-3.0) and is operated as a web application: the AGPL also obliges
whoever merely offers the software as a service to publish their changes. For
different terms, contact the copyright holder.
