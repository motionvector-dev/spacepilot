# SpacePilot — Cockpit

**Status**: Proposed, needs one yes/no from Saurabh
**Decided**: 2026-09-02
**Design system**: `DESIGN.md` at the repo root (spacepilot-design-system 2.5.0).
Not `~/code/design.md` — that is MotionVector's, a different product.

## The shape

Three shapes were on the table (`ARTIFACT-DIGEST.md`): flat top tabs as
shipped, three tiers Create/Cockpit/Console, and an eight-group ship-centric
sidebar. **The sidebar wins, cut from eight groups to five.**

1. This is an observability product. An observability product's navigation is
   its objects, not its verbs. The rail lists machines that exist.
2. Three tiers gate features by how expert you are. `CONCEPT.md` refuses
   persona modes, and that is what tiers are.
3. Flat tabs cap at about six items and have nowhere to put a second machine.
   A fleet grows sideways; tabs do not.
4. Only the rail shows "one local, one rented" without navigating anywhere.
   That sentence is the whole product.
5. A rail survives becoming a Tauri window. Top tabs fight the titlebar.

## The screens

| Screen | Shows | Fed by |
| --- | --- | --- |
| Glance `/cockpit` | Ships, docks, providers side by side; then runtimes ready, models that fit, numbers we actually measured | `/api/compute/local-profile`, `/api/cockpit/status`, `/api/runtimes`, `/api/compute/compatibility`, `/api/summary`, `/api/systems` |
| Ship `/cockpit/ship/:id` | What the machine has, where its memory ceiling came from, every runtime's state, every model's verdict with a reason, what it has actually run | `/api/compute/local-profile`, `/api/runtimes`, `/api/compute/compatibility`, `/api/summary`, `/api/systems` |
| Dock `/cockpit/dock/:id` | Rate, accrued, what an hour more would cost, instance state, the SSH hint | `/api/cockpit/status` |
| Runtimes `/cockpit/runtimes` | Install a runtime without a terminal — preview, install, downgrade confirm | `/api/runtimes`, `/{id}/preview`, `/{id}/install`, `/jobs/{id}` |
| Models `/cockpit/models` | Not built. The verdicts live on the ship screen; the hub that groups by task and downloads is M2 | `/api/compute/recipes` |
| Settings `/cockpit/settings` | Not built. Needs the token flow first | `/api/cockpit/config` |

Run history has no screen because it has no endpoint. `/api/summary` is
aggregate, not a log.

## What a fleet looks like

Today the fleet is one M1 Max and one AWS g6e.2xlarge, and the cockpit shows
both at once without either pretending to be the other.

The Mac is a **ship**. It keeps its own name — "MacBook Pro" — never an
instance id. Its numbers are current because the daemon runs on it. Its memory
ceiling says whether Metal reported it or we estimated it, because those are
different kinds of fact.

The g6e is a **dock**. It has an id, a rate, and a meter. It is stopped, so it
reads **asleep**, never offline or unavailable — it still exists and work can
wait for it. `$0.75/hr` sits on screen while it sleeps, so renting is a
decision you walked into rather than a default you fell through.

The corpus knows two more machines that are not here. The glance says "2, none
here now" instead of hiding them. A fleet of one, three times over, is not the
same as a fleet of three.

### Honest empty state, per widget

| Widget | Empty means | It says |
| --- | --- | --- |
| Providers | no endpoint exists | "no provider inventory yet… nothing rather than a count of zero" |
| Flown | nothing measured yet | stays empty; a spec sheet never fills it |
| Ship flown | machine not in the corpus | says the machine has no row, not that it is slow |
| Any field | route returned `null` | "not reported", in italics — never `0`, never `—` |
| Whole page | daemon down | one screen, no numbers, and the command to start it |

`0` and "we did not measure" look identical and mean opposite things. The
`Fact` component refuses to print a value it was not given.

## Chat sits in a palette, not a rail

**Command palette (⌘K), not a chat rail.** A rail costs a third of the width
of a data screen and is empty most of the time you are glancing. The cockpit's
job is a five-second read, not a conversation. The palette accepts plain
English, routes it to the same MCP tools an agent calls, and shows the reply
as a card in place — so "can this Mac run Wan 2.2" is one keystroke, and you
are still looking at the fleet. The long conversations belong in SpaceBar's
voice surface and in Claude Code, both of which already talk to the same MCP
server. Two chat boxes for one backend is a worse answer than one good palette.

## Browser agents

`spacepilot/mcp_server.py` already exposes 17 tools over MCP, and the cockpit
reads the same routes those tools call. The web hook is WebMCP: the page
declares its actions so a browser agent operates the cockpit without reading
pixels. WebMCP is a Web Machine Learning CG draft, not a standard — Chrome
runs an origin trial from 149, Edge has one, Firefox and Safari do not ship
it. So it is additive, never the only path to an action. Every action stays
reachable by click and by CLI.

## Milestones

| M | Ships | Passes when |
| --- | --- | --- |
| M1 | Glance and one detail view on real data, DESIGN.md tokens | Load `/cockpit` with the daemon up: every number traces to a route, and killing the daemon shows the down screen instead of zeroes |
| M2 | Spend gate, launch and stop a dock from the cockpit, settings | Starting the box states the rate and the ceiling before the call, and the meter matches `/api/cockpit/status` within one poll |
| M3 | Model hub, provider inventory, per-provider price and liveness | Providers stops being an empty state because a route now answers it |
| M4 | Command palette on MCP, WebMCP declarations, Tauri shell | A browser agent completes "install mlx-audio" with no pixel reading, and the same build runs as a desktop window |

## Ideas

Five things that are not built, each of which would earn a daily open.

1. **Would this fit?** — one field at the top of Glance. Paste a Hugging Face
   id, get the verdict against every machine you own before downloading
   anything. Uses the compatibility engine that already exists.
2. **The spend ceiling.** — set "$20 this month" once. A persistent bar, not a
   modal per run. It self-terminates the dock at the line and says so out
   loud. Renting stops being a decision you make forty times.
3. **Cheapest way to run this.** — pick a workload, see ship / dock / provider
   ranked by measured time and real money, with the flown numbers cited.
   The row you pick becomes the run. This is the product's thesis as a widget.
4. **Wake-on-work.** — queue a job against a sleeping dock. The cockpit shows
   "waiting for g6e · will cost about $0.40", starts it when you confirm,
   stops it when the job ends. Asleep-not-gone becomes usable, not just true.
5. **What changed since Tuesday.** — a diff strip: a runtime went stale, a
   model got a faster quant, your free disk dropped 40 GB. The map only
   compounds if someone reads the delta.

## What is not good today, and the fix

| Problem | Fix | Size |
| --- | --- | --- |
| Four PRs open 12 days, none referencing each other's layout | This branch merges the chain and picks the layout; land it and close 14/24/27/28 | ~40k |
| `web/cockpit.html` still ships the old tabbed screen on `/cockpit` server-side | Point `views.py` at the built React app, or delete the vanilla page | ~30k |
| Compute routes need `X-SpacePilot-Token`; the cockpit has no token flow, so every write button is a dead end | One token prompt, stored in memory, sent by the api client | ~60k |
| `/api/compute/local-profile` and `/api/runtimes` take seconds — runtimes shells out per package | Cache the runtime probe with an explicit "re-check" button | ~50k |
| No run history endpoint, so no run screen | Add `/api/runs`; the corpus already stores the rows | ~80k |
| Fonts come from Google's CDN — wrong for a local-first app and impossible in Tauri | Self-host Plus Jakarta Sans and JetBrains Mono in `web/fonts/` | ~20k |
| DESIGN.md declares no light palette; this branch derives one | Saurabh's call: keep it, or make SpacePilot dark-only and drop the toggle | ~15k either way |

**Decision needed:** DESIGN.md ships one palette and it is black. This branch
keeps a light theme behind an explicit toggle, defaulting to dark. Keep the
light theme, or go dark-only?
