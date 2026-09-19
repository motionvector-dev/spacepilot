# Modal Dashboard: Product Design & Frontend Technical Specification

> **Document Version**: 1.0  
> **Source Target**: Modal Cloud AI Infrastructure Web Console (`modal.com`)  
> **Target Audience**: Product Managers, Design Leads, and Frontend / Full-Stack Engineers  
> **Scope**: End-to-end teardown of UI/UX patterns, product architecture, information hierarchy, telemetry visualizations, state flows, and frontend component specifications.

---

## 1. Executive Summary & Product Architecture (PM Perspective)

Modal is a serverless cloud compute platform engineered specifically for AI/ML workloads, distributed pipelines, and GPU acceleration. Its web interface acts as a mission-control dashboard where developers and ML engineers monitor cold-start latencies, trace function call executions, inspect container health, tail live stdout/stderr streams, track GPU spend down to fractional cents, and spin up one-click LLM inference endpoints.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               GLOBAL TOP NAVIGATION BAR                                │
│ [Modal Logo] [katana-video ▾] [main ▾]   [🔍 ⌘K Search]  [● Workspace Metrics] [$22.67] │
├───────────────┬────────────────────────────────────────────────────────────────────────┤
│ PRIMARY TABS  │ Apps  |  Endpoints [New]  |  Logs  |  Containers  |  Secrets  | ...    │
├───────────────┴────────────────────────────────────────────────────────────────────────┤
│ MAIN WORKSPACE VIEWPORT                                                                │
│ ┌───────────────────────┬────────────────────────────────────────────────────────────┐ │
│ │ LEFT SUB-SIDEBAR      │ CENTRAL CONTENT PANE                                       │ │
│ │ • Overview            │ • Time Range Controls: [1d | 1mo] [Timezone Picker]        │ │
│ │ • Deployment History  │ • Real-Time Aggregate Histogram / Success-Failure Heatmap  │ │
│ │ • App Logs            │ • Tab Switcher: Calls | Containers | Metrics | Details     │ │
│ │ • Usage               │ • Interactive Data Grid (Virtual Table with Live Status)   │ │
│ │ • Function Selector   │ • Right Slide-Over Inspector Drawer (Logs, Live Charts)    │ │
│ └───────────────────────┴────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Core Product Tenets & UX Principles
1. **High Information Density with Zero Clutter**: Surfaces hundreds of concurrent container runs and microsecond metrics without overwhelming the user through compact tables, inline status pills, and micro-sparklines.
2. **Real-Time Observability by Default**: Every operational screen (logs, container states, call histories) connects via streaming channels (SSE/WebSockets) with live indicator pulses (`🟢 Live`, `🔄 Streaming`).
3. **Frictionless Drill-Down**: 3-click hierarchy from Global Workspace Fleet → App → Function → Individual Container Execution → Real-Time Telemetry & Shell Access.
4. **Developer-Native Workflows**: Embedded CLI commands (`modal shell <id>`, `modal endpoint create ...`), copy triggers on all identifiers (`fu-...`, `ta-...`, `ap-...`), and instant keyboard accessibility via `⌘K`.

---

## 2. Comprehensive Screen-by-Screen Product Breakdown

Based on the 17 desktop captures, here is the granular breakdown of every functional view:

### 2.1. Apps Overview & Function Registry (`/apps/[workspace]/[env]`)
*Screenshot 1*

* **Header Controls**:
  * Environment & Workspace Scope indicators.
  * Filter pills: `Live Apps (9)` with green status badge, `Stopped Apps (7)` with neutral counter.
  * Sorting selector: `Sort By: Most recent ▾`.
  * Inline search input: `Search or filter` with shortcut hint `/`.
  * Direct action: `[Quickstart guide]` button.
* **App Container Card (Accordion Structure)**:
  * Top Metadata: Application identifier (`video-upscaler-prod-v1`), author chip (`sam-12`), relative deployment time (`2 days ago`).
  * Nested Function Row Architecture:
    * **Status Indicator**: Neutral dot for idle functions; pulsing green `🟢` dot with active worker counter (e.g. `2 containers, 2 inputs`) for active workers.
    * **Function Name**: Monospace label (e.g. `streamed_step`, `run_pipeline`, `warm_flashvsr`).
    * **Hardware / Runtime Badges**: Explicit compute tier tag (e.g. `CPU`, `L40S GPU`, `T4 GPU`) and routing tag (`Web Function`).
    * **Micro-Sparkline**: 24-hour hourly activity bar chart illustrating throughput and error ticks directly inside the table row.

---

### 2.2. Function Details & Execution History (`/apps/.../functions`)
*Screenshots 2 & 3*

* **Function Hero Header**:
  * Breadcrumb: `video-upscaler-prod-v1 / streamed_step` with single-click ID copy button.
  * Live runtime chips: `Containers: 1 live`, `Calls: 1 running`.
  * Time scrubber controls: Step backward `[<<]`, Pause live refresh `[||]`, Step forward `[>>]`.
  * Time range dropdown: Quick selection (`1d`, `1mo`) with local timezone preview (`GMT+5:30`).
  * Deployment overlay toggle: `Show Deployments` switch.
* **Call Results Timeline Histogram**:
  * 24-hour / 30-day time series bar chart.
  * Stacked color coding: Green bars for successful invocations, Red bars for exceptions/failed runs.
* **Navigation Sub-Tabs**:
  * `Function Calls` (Active), `Containers (10+ errors badge)`, `Metrics`, `Details`, `Files`, `Try It [Beta]`.
* **Execution Data Table**:
  * Filter: `Status: Any ▾` dropdown, `[Clear queue ⊗]` button.
  * Columns: `Enqueued (Timestamp)`, `Started (Timestamp)`, `Startup (Cold start latency in seconds)`, `Execution (Duration)`, `Status`.
  * Row Actions: In-flight calls feature a direct `[Cancel ⊗]` action button.

---

### 2.3. Live App Logs & Terminal Stream (`/apps/.../logs`)
*Screenshot 4*

* **Telemetry Header**:
  * 1-hour log volume histogram chart for rapid spike detection.
  * Active filter token: `function:streamed_step [✕]`.
  * Controls: `[✣ Collapse logs]` and `[⚙ Settings]`.
* **Stream Viewer**:
  * Two-column layout: Fixed `Timestamp` column (`Sep 01 19:50:32.144`) and formatted `Content` log message.
  * Color-coded status dots: Orange indicator for stderr/warnings/TensorRT cache notices, Blue indicator for stdout and step metrics.
  * Persistent footer status: `🔄 Streaming` indicator.

---

### 2.4. App Cost & Granular Usage Analytics (`/apps/.../usage`)
*Screenshot 5*

* **Billing Scope**:
  * Billing cycle navigation: `[ < 🗓 Billing Cycle: Sep 1 – Oct 1, 2026 ▾ > ]`.
  * Big Metric Display: Total accumulated spend in USD (e.g. `$7.34`).
* **24-Hour Usage Distribution Bar Chart**:
  * Time selector toggle: `[Last hour | Last 24h]`.
  * Multi-colored stacked bar chart breaking down spend per hourly bucket across hardware resources.
* **Cycle Resource Breakdown Matrix**:
  * Resource cost ledger:
    * 🔵 `L40S GPU`: `$5.65`
    * 🟢 `CPU`: `$1.16`
    * 🟡 `Memory`: `$0.43`
    * 🟣 `T4 GPU`: `$0.11`
  * Direct deep-link: `View all rates ↗`.
  * Projected monthly burn progress chart.

---

### 2.5. Managed Inference Endpoints (`/endpoints`) [New Feature]
*Screenshot 6*

* **Product Purpose**: Turnkey model serving allowing users to deploy open-weight foundation models without writing orchestration code.
* **Model Catalog Showcase**:
  1. `Kimi K3` (`moonshotai/Kimi-K3`) — "Frontier open-weights model for coding, reasoning, and long context."
  2. `Qwen3.6 35B A3B` (`Qwen/Qwen3.6-35B-A3B`) — "Model tuned for fast chat, reasoning, and extraction."
  3. `Gemma 4 E4B IT` (`google/gemma-4-E4B-it`) — "Compact instruction model for lightweight workloads."
* **Card Architecture**:
  * Model avatar, name, Hugging Face org path, short description.
  * Embedded CLI one-liner snippet: `modal endpoint create --model ...` with copy icon.
  * Action button: `[Deploy this model ->]`.
* **Footer Callout**:
  * "Deploy any model" banner with link to docs and `[Browse all models]` modal.

---

### 2.6. Global Logs & App Lifecycle Fleet (`/logs`)
*Screenshot 7*

* **Fleet Table Columns**: `Name`, `State`, `Created`, `Stopped`.
* **State Taxonomy**:
  * `deployed` (with green waveform icon and `Currently running` status).
  * `deployed` (with neutral state and `Currently idle` status).
  * `stopped` (ephemeral runs such as `quota-check`, `x264-bench`, `modal shell`).
* **Row Actions**: Instant `[Stop now]` button for deployed applications.

---

### 2.7. Global Containers View (`/containers`)
*Screenshot 8*

* **Summary Bar**: "There are 3 containers running in environment main."
* **Filter Pills**: `[🟢 All 3]`, `[Functions 3]`, `[Sandboxes 0]`.
* **Search Input**: `[🔍 Search containers      /]`.
* **Fleet Table**:
  * `App`: Target app name.
  * `Created by`: User handle avatar chip.
  * `CPU ↓`: Dynamic live mini-bar chart with sort indicator.
  * `Memory`: Quantitative memory bar and text label (e.g. `1.2 GiB`, `388.7 MiB`).
  * `Started`: Relative timestamp (`2 minutes ago`).

---

### 2.8. Container Details Slide-Over Drawer
*Screenshots 9, 10 & 11*

* **Slide-Over Header**:
  * Container ID: `ta-01M1EM9HWS71Z38C3DG2WEX75R` with copy trigger.
  * Associated Function ID: `fu-Jb8k3Hw5T27UqdzBFa4Ctd`.
  * Interactive Shell Snippet: `modal shell <id>` for instant terminal debugging.
  * Metadata summary: Status (`🟣 Live` / `🟢 Done`), Startup time (`4.66s`), Worker Type (`CPU`).
  * Top Drawer Actions: `[Stop ⊗]`, Expand Fullscreen `[⇲]`.
* **Drawer Tabs**: `Logs`, `Metrics`, `Inputs`, `Live Profiling`.
* **Live Multi-Metric Quad-Chart**:
  1. **Running calls**: Line graph tracing active concurrency.
  2. **CPU cores used**: Multi-line graph comparing `Used` (green) vs `Reserved` (gray threshold).
  3. **Memory used**: Multi-line graph comparing `Used` (orange) vs `Reserved` (gray threshold).
  4. **Network**: Dual-line graph comparing `Egress` (purple) vs `Ingress` (pink) in KB/s.
* **Interactive Tooltip System**:
  * Hovering across any chart reveals synchronized crosshair timestamp and precise float metrics across all 4 visualizers.

---

### 2.9. Workspace Metrics Flyout & Telemetry
*Screenshot 12*

* **Right Drawer Flyout**: Triggered by clicking `● Workspace metrics` in the top navigation bar.
* **Environment Filter**: `Environments: All ▾`.
* **Top Metric Scorecards**:
  * `Total containers`: `0` (Limit: 100)
  * `Live sandboxes`: `0`
  * `Pending sandboxes`: `0`
  * `Total GPUs`: `0` (Limit: 10)
* **Visualizer Tabs**: `Usage over time` (Active), `Breakdown`.
* **Stacked Multi-App Area Graph**:
  * Dynamic resource selection dropdown (`Resource: Containers ▾`).
  * Shows historical concurrency volume stacked by individual application color legend.

---

### 2.10. Global Command Palette (`⌘K`)
*Screenshot 13*

* **Trigger**: `⌘K` keyboard shortcut or clicking top search bar.
* **Modal Overlay**: Centered modal with search input `Enter an ID or search...`.
* **Categorized Command List**:
  * **Usage**: `Workspace metrics`, `Usage & billing`, `Workspace limits`.
  * **Navigation**: `Apps`, `Logs`, `Containers`, `Secrets`, `Storage`, `Notebooks`.
* **Footer Keyboard Legend**: `↵ Open`, `↑↓ Select`, `esc Close`.

---

### 2.11. Settings & Workspace Governance
*Screenshots 14, 15, 16 & 17*

* **Settings Navigation Tree**:
  * `‹ Back to Dashboard`
  * **Account**: Profile, Workspaces, Email preferences.
  * **Workspace**: Resource limits.
  * **Tokens**: API tokens, Proxy tokens.
  * **Features**: Domains, Image builder version, Proxies [Beta].
* **Profile Settings (`/settings/profile`)**:
  * Avatar upload, Email update input.
  * Preferences: Timezone selection (`Browser Local Time (GMT+5:30)`), Appearance theme (`Dark`).
  * Connected OAuth accounts table (`GitHub: unfoundbox`).
* **Workspaces Management (`/settings/workspaces`)**:
  * Organization table with roles (`Owner`, `Member`).
  * Actions: `Copy ID`, `Manage members`, `Leave`.
  * GitHub Org automatic discovery with `[Refresh Orgs]` trigger.
* **Email Preferences (`/settings/notifications`)**:
  * Master switch: `All notifications`.
  * System Notification Toggles: Deployed Function alerts, Failure digests, Usage alerts, Client deprecation warnings.
  * Marketing Notifications: Product updates toggle.
* **Resource Limits & Quota Monitoring (`/settings/.../limits`)**:
  * Accordion Table with 30-Day Peak Visualizers:
    1. `GPU limit`: Cap (10), Current (0%), Peak (70%), 30-day peak line chart with limit threshold.
    2. `Container limit`: Cap (100), Current (2%), Peak (18%), 30-day peak line chart with limit threshold.
    3. `Sandbox creation rate limit`: Cap (5/s + 150 burst), Current (0/s), Peak (1/s).

---

## 3. Frontend Architecture & Technical Specification (Developer Perspective)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        COMPONENT HIERARCHY TREE                        │
└────────────────────────────────────────────────────────────────────────┘
<AppRoot>
 ├── <GlobalBanner />              // Announcement banner
 ├── <TopNavBar>
 │    ├── <WorkspaceEnvSelector /> // Dual dropdown
 │    ├── <CommandPaletteTrigger />// ⌘K modal opener
 │    ├── <WorkspaceMetricsPill /> // Flyout drawer opener
 │    ├── <CreditsBadge />         // Balance pill
 │    └── <UserProfileMenu />      // Avatar & settings link
 ├── <SubNavTabs />                // Route switcher: Apps, Endpoints, Logs...
 └── <MainLayout>
      ├── <SidebarNav />           // Overview, Logs, Usage, Function list
      ├── <ContentArea>
      │    ├── <TimeScrubber />    // Range & timezone controls
      │    ├── <MetricHistogram /> // Canvas/SVG time-series chart
      │    └── <DataTable />       // Virtualized rows with micro-sparklines
      └── <DrawerPortal>           // Slide-over for container inspector / metrics
           ├── <DrawerHeader />    // Container ID, CLI snippet, status chip
           ├── <StreamingLogView />// Virtual terminal stream with ANSI parser
           └── <QuadMetricCharts />// Synchronized live line charts
```

### 3.1. Design System Tokens & Foundations

#### Color Palette (Dark Theme First)
* **Background Surfaces**:
  * Root Background (`--bg-root`): `#0c0d0e` or `#0e1011`
  * Card / Panel Surface (`--bg-surface`): `#141719`
  * Card Surface Hover (`--bg-surface-hover`): `#1a1e22`
  * Popover / Drawer Overlay (`--bg-overlay`): `#121417`
  * Border / Divider (`--border-subtle`): `#23272c`
  * Border Focused (`--border-focus`): `#383f47`
* **Brand & Accent Colors**:
  * Modal Primary Green (`--brand-green`): `#00e575` / `#10b981` (Used for logo, live status dots, success charts)
  * Running / Active Purple (`--status-running`): `#a855f7`
  * Error / Failed Red (`--status-error`): `#ef4444` / `#f87171`
  * Warning Orange (`--status-warning`): `#f59e0b`
  * Telemetry Ingress Pink (`--metric-pink`): `#ec4899`
  * Telemetry Egress Purple (`--metric-purple`): `#8b5cf6`
* **Typography**:
  * Primary UI Font: `Inter`, system-ui, sans-serif
  * Monospace / Code Font: `JetBrains Mono`, `Geist Mono`, `SF Mono`, monospace
  * Numerical Rule: Strictly use `font-variant-numeric: tabular-nums;` across all timestamps, execution latencies, and metric values.

---

### 3.2. State Management & Real-Time Data Flow

```
┌─────────────────┐       WebSocket / SSE       ┌────────────────────────┐
│  Modal Backend  │ ──────────────────────────> │   Frontend StreamBus   │
└─────────────────┘                             └───────────┬────────────┘
                                                            │
                     ┌──────────────────────────────────────┼────────────────────────┐
                     ▼                                      ▼                        ▼
         ┌──────────────────────┐               ┌───────────────────────┐  ┌──────────────────┐
         │  Terminal Log Store  │               │ Metrics Time-Series   │  │  Container Fleet │
         │  (Circular Buffer)   │               │ (Sliding Window Ring) │  │  (Status Map)    │
         └──────────────────────┘               └───────────────────────┘  └──────────────────┘
```

1. **Log Stream Architecture**:
   * Must use a **circular memory buffer** (max 5,000 lines in DOM) with DOM virtualization (e.g. `@tanstack/react-virtual`).
   * Colorizes ANSI escape codes and parses timestamp prefixes on the fly.
   * Auto-scroll behavior: Locks to bottom unless user scrolls upward; displays a floating "Resume scroll" pill when scrolled back.
2. **Chart Synchronization & Hover Crosshairs**:
   * The 4 container metrics charts (`Running calls`, `CPU`, `Memory`, `Network`) share a single synchronized hover state `activeTimestamp`.
   * When cursor hovers over any point in chart #1, a synchronized vertical crosshair guide and tooltip render across all 4 charts at that exact timestamp.
3. **Timezone Normalization Engine**:
   * All raw UTC timestamps received from API endpoints are passed through a global timezone formatter context.
   * Users can toggle between `Browser Local Time (GMT+X)` and `UTC`, which immediately re-renders table timestamps and chart X-axes without refetching.

---

### 3.3. Key Frontend Component Implementation Details

#### 1. Micro-Sparkline Table Cell (`<SparklineBarChart />`)
* **Input Props**: `data: { timestamp: number, count: number, hasErrors: boolean }[]`, `height?: number`.
* **Rendering**: Pure SVG / lightweight HTML bars.
* **Interaction**: Hovering over individual bars reveals mini-tooltip with timestamp and execution count.

#### 2. Slide-Over Inspector Drawer (`<InspectorDrawer />`)
* **Behavior**:
  * Slides in from the right edge (`transform: translateX(0)` with CSS spring transition).
  * Does not cause reflow of underlying table; background page maintains scroll position.
  * Supports responsive fullscreen expand toggle (`[⇲]`).
  * Keyboard trigger: `Esc` closes active drawer.

#### 3. Command Palette (`<CommandPalette />`)
* **Behavior**:
  * Global event listener for `KeyDown` matching `(e.metaKey || e.ctrlKey) && e.key === 'k'`.
  * Fuzzy search matching over registered application routes, documentation links, and active container IDs.
  * Direct action execution on `Enter` (e.g. navigation, opening modals).

---

## 4. Product Roadmap & Strategic UX Recommendations

1. **Integrated Cold-Start Profiling**:
   * Modal displays startup time (e.g. `10.95s`, `4.66s`). Adding an expandable breakdown showing (Image pull -> Container init -> Model download -> GPU warmup) would give engineers instant insight into optimization bottlenecks.
2. **One-Click Cost Alerts**:
   * From the Usage tab, allow developers to click `[+ Set Budget Alert]` directly on specific high-cost GPUs (such as L40S) to receive automated Slack/email notifications.
3. **Interactive Log Filtering**:
   * Add regex search, level toggles (`[Errors Only]`, `[Warnings]`), and single-click copy of execution tracebacks directly inside the App Logs viewer.

---

## 5. Strategic UI/UX & Product Design Inspiration for AgentWorth

> **Comparative Context**: Analysis of AgentWorth's local session telemetry dashboard (`http://localhost:3000/s/agent-ac2acdc8816e1c225`) juxtaposed against Modal's cloud infrastructure console. While AgentWorth operates on local developer machines auditing autonomous coding agents (Claude Code, Antigravity, Cursor, Codex, etc.) and Modal operates on cloud serverless GPU containers, both systems share the core mission of **grounded, high-density observability for non-deterministic AI execution**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              AGENTWORTH × MODAL: OBSERVABILITY PARADIGM COMPARISON                     │
├──────────────────────────┬─────────────────────────────────┬───────────────────────────┤
│ Observability Dimension  │ Modal Infrastructure Console    │ AgentWorth Opportunity    │
├──────────────────────────┼─────────────────────────────────┼───────────────────────────┤
│ Execution Density        │ Micro-sparklines per function   │ Inline token/event ticks  │
│ Telemetry Inspection     │ Quad-chart with hover sync      │ Pacing & Context Growth   │
│ Fast Navigation          │ Global ⌘K Command Palette       │ Agent/Session ⌘K Engine   │
│ FinOps / Cost Accounting │ Stacked 24h resource bars       │ Stacked model cache spend │
│ Master-Detail Hierarchy  │ Persistent sub-nav & function list Split Explorer navigation │
│ CLI Interactivity        │ `modal shell <id>` one-click    │ `agentworth replay <id>`  │
└──────────────────────────┴─────────────────────────────────┴───────────────────────────┘
```

### 5.1. High-Priority Product & UX Inspirations for AgentWorth

#### 1. Micro-Event Sparklines in the Traces Explorer Table
* **Modal Pattern**: Every function row in Modal's app table embeds a 24-hour micro-sparkline showing hourly execution volume and colored error ticks inline.
* **AgentWorth Current State**: The `TracesExplorer` table displays rows with static text columns (`Session ID`, `Agent`, `Models`, `Duration`, `Total Tokens`, `Verdict Badge`).
* **Proposed Enhancement**:
  * Embed an inline **Session Trajectory Sparkline** in each trace row:
    * Step-by-step horizontal bar chart showing token accumulation rate across turns.
    * Color-coded event markers: 🟢 Tool Success (green tick), 🔴 Tool / Shell Failure (red tick), 🟡 Model Thinking / Reasoning turn (amber tick).
  * **Value**: Enables developers to visually spot long-running stuck loops or turbulent recovery spirals before even opening the trace.

#### 2. Synchronized Session Telemetry Quad-Chart (Pacing & Context Growth)
* **Modal Pattern**: Modal's container drawer renders 4 synchronized live charts (`Running Calls`, `CPU`, `Memory`, `Network`) with a single unified hover crosshair revealing synchronous float metrics at that exact millisecond.
* **AgentWorth Current State**: In `SessionInspector`, session stats (tokens, duration, models, outcome) are listed in a static text sub-header ribbon, followed by a vertical sequence of cards.
* **Proposed Enhancement**:
  * Introduce an interactive **Session Pacing & Telemetry Drawer Header**:
    1. **Context Window Growth Curve**: Input + Cache + Output tokens plotted over step sequence number against the model's maximum context limit.
    2. **Turn Latency & Thinking Time**: Dual-bar tracking model reasoning time vs tool/shell execution duration per turn.
    3. **File & AST Churn**: Additions (`+`) vs Deletions (`-`) lines across turns.
    4. **Cumulative List-Price Cost**: Step-by-step USD cost ramp showing the exact inflection point where prompt caching activated or failed.
  * Hovering across any point in the chart highlights the corresponding event card in the timeline below.

#### 3. Command Palette (`⌘K`) for Instant Cross-Agent Exploration
* **Modal Pattern**: A centralized `⌘K` modal offering quick-jump navigation across apps, storage, logs, and settings.
* **AgentWorth Current State**: Users manually scroll through the landing page, click into Explorer, and use dropdown filters for adapters and models.
* **Proposed Enhancement**:
  * Build an `agentworth` native `⌘K` palette:
    * Filter by adapter syntax: `agent:claude`, `agent:agy`, `agent:cursor`.
    * Jump directly to file touched: `file:api.ts`, `file:SessionInspector.tsx`.
    * Jump by outcome rung: `rung:ci-verified`, `rung:claim-only`.
    * Instant search for session IDs and shell command invocations (e.g. `cmd:pytest`).

#### 4. Stacked Model FinOps & Cache Savings Breakdown
* **Modal Pattern**: Modal's Usage view features a 24h stacked bar chart breaking down spend per hourly bucket by resource type (`L40S`, `CPU`, `Memory`, `T4`) alongside total billing cycle burn.
* **AgentWorth Current State**: AgentWorth has the static `HeroReceipt` and `CacheCliffWidget`, but lacks a historical time-series breakdown of fleet spend.
* **Proposed Enhancement**:
  * Add a **Historical Burn & Model FinOps Tab**:
    * Daily/weekly stacked bar chart showing spend segmented by AI model family (`Claude 3.7 Sonnet (Thinking)`, `Gemini 2.5 Pro`, `DeepSeek V3`, `Qwen 2.5 Coder`).
    * **Prompt Cache ROI Overlay**: A visual stacked comparison showing *Gross Cost (List Price)* vs *Net Cost (After 90% Prompt Cache Discount)* to prove financial efficiency.

#### 5. Persistent Master-Detail Layout for Explorer Mode
* **Modal Pattern**: Left sidebar stays pinned with sub-navigation (`Overview`, `Deployment History`, `App Logs`, `Usage`, and function list), making navigation effortless without vertically scrolling past large hero elements.
* **AgentWorth Current State**: In explorer mode, the user scrolls vertically past the `HeroReceipt`, `VerdictBoard`, `ArchaeologyPanel`, and `TracesExplorer`.
* **Proposed Enhancement**:
  * Introduce a docked 3-pane workbench view in Explorer mode:
    * **Left Rail**: Adapter selector, outcome rungs filter, and time window presets.
    * **Center Pane**: Virtualized traces table with sparklines.
    * **Right Slide-Over / Split View**: Pinned `SessionInspector` and `ExportModal`.

#### 6. Embedded Diagnostic CLI Actions
* **Modal Pattern**: Direct CLI snippet triggers (`modal shell <container_id>`) right inside the container header with single-click copy.
* **AgentWorth Current State**: AgentWorth has a copy button for the session ID.
* **Proposed Enhancement**:
  * Add actionable developer commands in the `SessionInspector`:
    * `agentworth inspect <session_id>`
    * `agentworth diff <session_id>`
    * `agentworth replay <session_id> --step <sequence_num>`

