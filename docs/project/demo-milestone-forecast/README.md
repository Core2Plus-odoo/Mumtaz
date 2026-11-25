# Milestone forecast — browser check

Run on 25 Nov 2026 in an isolated development container on **stock Odoo 19,
not Mumtaz_C2P**. Fictional data only. Nothing installed or deployed anywhere.

Signed in as an ordinary project manager ("Shafat (demo, delivery owner)"),
not the administrator.

| Screen | What it shows |
|---|---|
| `F1-milestone-list-health` | Four milestones: green (on time), amber (3 days late), red (9 days late), grey "No forecast" |
| `F2-milestone-form-amber` | Commitment date, forecast date, calculated health and the history panel |
| `F3-refused-without-reason` | Forecast moved with no reason: the save is refused |
| `F4-saved-with-reason-in-history` | Same change with a reason: old and new date and the reason in one history entry; health now red |
| `F5-project-form-worst-milestone` | The project shows red, its worst milestone |

Also read back from the server after the run: a project whose only milestone is
on time shows green, and a project whose only milestone has no forecast shows
grey.

Not checked in a browser: reached milestones, editing dates in the list view,
clearing a date, the commitment-date change.
