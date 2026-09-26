import { Link } from 'react-router-dom'

import useAdminAnalytics, { ANALYTICS_WINDOWS } from '../hooks/useAdminAnalytics'
import { accessibility, colors, fonts, spacing } from '../styles/theme'

/**
 * /admin — the player analytics report for the accounts in HOV_ADMIN_USER_IDS.
 *
 * Presentation only: the data and its window come from `useAdminAnalytics`,
 * and every number's definition lives with the query that computes it
 * (src/api/services/analytics_report.py). Each section's id is its report key;
 * `Section` reads that section's scope (windowed, rolling or all-time) from the
 * report, so a label here can never claim a window the query did not use. A
 * section the server could not compute arrives as `{error: 'unavailable'}` and
 * is shown as such, so one bad query never blanks the page, and any single
 * value the report does not carry renders as MISSING rather than crashing.
 */


// A day with any activity keeps a visible sliver rather than rounding to nothing.
const MIN_VISIBLE_BAR_PCT = 3

// Shown for any value the report did not carry (or had nothing to average).
const MISSING = '—'

const panel = { background: colors.bg.panel, padding: spacing.lg, marginBottom: spacing.lg }

const styles = {
    page: {
        minHeight: '100vh',
        background: colors.bg.main,
        color: colors.text.main,
        fontFamily: fonts.main,
        padding: spacing.lg,
        boxSizing: 'border-box',
    },
    inner: { maxWidth: '1100px', margin: '0 auto' },
    header: {
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        marginBottom: spacing.xl,
    },
    title: { color: colors.primary, margin: 0, fontSize: '1.4rem', letterSpacing: '0.1em' },
    controls: { display: 'flex', flexWrap: 'wrap', gap: spacing.sm, alignItems: 'center' },
    button: (active) => ({
        minHeight: accessibility.touchTarget,
        padding: `0 ${spacing.md}`,
        fontFamily: fonts.main,
        fontSize: '0.9rem',
        cursor: 'pointer',
        touchAction: 'manipulation',
        background: active ? colors.alpha.primary[20] : 'transparent',
        color: active ? colors.primary : colors.text.main,
        border: `1px solid ${active ? colors.primary : colors.border.main}`,
    }),
    link: {
        color: colors.accent,
        minHeight: accessibility.touchTarget,
        display: 'inline-flex',
        alignItems: 'center',
    },
    summary: {
        color: colors.text.muted,
        cursor: 'pointer',
        minHeight: accessibility.touchTarget,
        display: 'flex',
        alignItems: 'center',
        fontSize: '0.85rem',
    },
    section: { ...panel, border: `1px solid ${colors.border.main}` },
    errorBox: { ...panel, border: `1px solid ${colors.danger}` },
    errorText: { color: colors.danger, marginTop: 0 },
    heading: { color: colors.secondary, margin: `0 0 ${spacing.md} 0`, fontSize: '1rem', letterSpacing: '0.08em' },
    scope: { color: colors.text.muted, fontSize: '0.8rem', letterSpacing: 0 },
    subheading: { color: colors.text.muted, margin: `${spacing.md} 0 ${spacing.sm} 0`, fontSize: '0.85rem' },
    tiles: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: spacing.md,
    },
    tile: { border: `1px solid ${colors.border.light}`, padding: spacing.md },
    tileValue: { color: colors.text.bright, fontSize: '1.8rem', lineHeight: 1.1 },
    tileLabel: { color: colors.text.muted, fontSize: '0.8rem', marginTop: spacing.xs },
    tableWrap: { overflowX: 'auto' },
    table: { borderCollapse: 'collapse', width: '100%', fontSize: '0.85rem' },
    th: {
        textAlign: 'left',
        color: colors.text.muted,
        fontWeight: 'normal',
        borderBottom: `1px solid ${colors.border.main}`,
        padding: `${spacing.xs} ${spacing.sm}`,
        whiteSpace: 'nowrap',
    },
    td: { padding: `${spacing.xs} ${spacing.sm}`, borderBottom: `1px solid ${colors.border.light}` },
    num: { textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
    muted: { color: colors.text.muted },
    chart: {
        display: 'flex',
        alignItems: 'flex-end',
        gap: '2px',
        height: '96px',
        borderBottom: `1px solid ${colors.border.main}`,
    },
    bar: (fraction) => ({
        flex: '1 1 0',
        minWidth: '3px',
        height: `${fraction > 0 ? Math.max(fraction * 100, MIN_VISIBLE_BAR_PCT) : 0}%`,
        background: colors.primary,
        borderRadius: '4px 4px 0 0',
    }),
    chartAxis: {
        display: 'flex',
        justifyContent: 'space-between',
        color: colors.text.muted,
        fontSize: '0.75rem',
        marginTop: spacing.xs,
    },
}

// -- value formatting --------------------------------------------------------

/** A section the server failed to compute, or left out of the report. */
function isSectionUnavailable(section) {
    return section == null || (typeof section === 'object' && !Array.isArray(section) && 'error' in section)
}

const isNumber = (v) => typeof v === 'number' && Number.isFinite(v)

/** `part` of `whole` as a whole percentage. */
function share(part, whole) {
    return isNumber(part) && isNumber(whole) && whole ? `${Math.round((100 * part) / whole)}%` : MISSING
}

/** A number already in percent. */
function percent(value) {
    return isNumber(value) ? `${value}%` : MISSING
}

/** One decimal place. */
function oneDecimal(value) {
    return isNumber(value) ? value.toFixed(1) : MISSING
}

/** `Cave Entrance (14, 5)`, or just the room for a save without a tile. */
function roomLabel(stall) {
    const room = stall.room ?? MISSING
    return isNumber(stall.x) && isNumber(stall.y) ? `${room} (${stall.x}, ${stall.y})` : room
}

function scopeLabel(scope, windowDays) {
    if (scope === 'window') return `last ${windowDays} days`
    if (scope === 'all_time') return 'all time'
    if (scope === 'rolling') return 'rolling 24h / 7d / 30d'
    return null
}

// -- building blocks ---------------------------------------------------------

const isEmptyList = (data) => Array.isArray(data) && data.length === 0

/**
 * A report section: heading, scope, and the unavailable/empty states, so each
 * section body only renders data it is guaranteed to have.
 *
 * `children` is a function of the section's data. A list section is empty when
 * the list is; an object section decides emptiness per sub-table.
 */
function Section({ id, title, report, children }) {
    const headingId = `admin-${id}`
    const data = report[id]
    const scope = scopeLabel(report.scope?.[id], report.window_days)
    let body
    if (isSectionUnavailable(data)) {
        body = <p style={styles.muted}>Unavailable — the server could not compute this section.</p>
    } else if (isEmptyList(data)) {
        body = <Empty />
    } else {
        body = children(data)
    }
    return (
        <section aria-labelledby={headingId} style={styles.section}>
            <h2 id={headingId} style={styles.heading}>
                {title}
                {scope && <>{' '}<span style={styles.scope}>({scope})</span></>}
            </h2>
            {body}
        </section>
    )
}

function Empty() {
    return <p style={styles.muted}>No data yet.</p>
}

function Tile({ value, label }) {
    return (
        <div style={styles.tile}>
            <div style={styles.tileValue}>{value ?? MISSING}</div>
            <div style={styles.tileLabel}>{label}</div>
        </div>
    )
}

/** A small table. `columns` is [{key, label, numeric?, render?}]. */
function Table({ label, columns, rows }) {
    return (
        <div style={styles.tableWrap}>
            <table aria-label={label} style={styles.table}>
                <thead>
                    <tr>
                        {columns.map((c) => (
                            <th key={c.key} scope="col" style={{ ...styles.th, ...(c.numeric ? styles.num : null) }}>
                                {c.label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {/* Rows are a server snapshot with no stable id, never reordered in place. */}
                    {rows.map((row, i) => (
                        <tr key={i}>
                            {columns.map((c) => (
                                <td key={c.key} style={{ ...styles.td, ...(c.numeric ? styles.num : null) }}>
                                    {c.render ? c.render(row) : (row[c.key] ?? MISSING)}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

/** The failure message with a Retry; `style` frames it once the page is showing. */
function ErrorRetry({ error, onRetry, style }) {
    return (
        <div role="alert" style={style}>
            <p style={styles.errorText}>⚠ {error}</p>
            <button type="button" onClick={onRetry} style={styles.button(false)}>Retry</button>
        </div>
    )
}

/** A titled table, or "No data yet" when it has no rows (or none were sent). */
function SubTable({ title, label = title, columns, rows }) {
    return (
        <>
            <h3 style={styles.subheading}>{title}</h3>
            {rows?.length ? <Table label={label} columns={columns} rows={rows} /> : <Empty />}
        </>
    )
}

/**
 * One series of daily bars. Every bar carries its date and value as its
 * accessible name and hover title, so nothing is conveyed by height alone.
 * Only rendered for a non-empty `daily` (Section filters empty lists).
 */
function DailyBars({ title, daily, field, unit }) {
    const max = Math.max(0, ...daily.map((d) => d[field]).filter(isNumber))
    return (
        <div>
            <h3 style={styles.subheading}>{title} (peak {max})</h3>
            <div style={styles.chart}>
                {daily.map((d) => {
                    const value = isNumber(d[field]) ? d[field] : 0
                    const label = `${d.day}: ${d[field] ?? MISSING} ${unit}`
                    return <div key={d.day} role="img" aria-label={label} title={label} style={styles.bar(max ? value / max : 0)} />
                })}
            </div>
            <div style={styles.chartAxis}>
                <span>{daily[0].day}</span>
                <span>{daily[daily.length - 1].day}</span>
            </div>
        </div>
    )
}

const PLAYERS_COLUMN = { key: 'players', label: 'Players', numeric: true }

// -- sections, in report order -----------------------------------------------

function PlayersSection({ id, report }) {
    return (
        <Section id={id} title="Players" report={report}>
            {(players) => (
                <div style={styles.tiles}>
                    <Tile value={players.total_accounts} label="accounts" />
                    <Tile value={players.started_playing} label="have played" />
                    <Tile value={players.new_accounts?.['7d']} label="new in 7d" />
                    <Tile value={players.active?.dau} label="active in 24h" />
                    <Tile value={players.active?.wau} label="active in 7d" />
                    <Tile value={players.active?.mau} label="active in 30d" />
                </div>
            )}
        </Section>
    )
}

function DailySection({ id, report }) {
    return (
        <Section id={id} title="Daily" report={report}>
            {(daily) => (
                <>
                    <DailyBars title="Active players" daily={daily} field="active" unit="active players" />
                    <DailyBars title="Signups" daily={daily} field="signups" unit="signups" />
                    <DailyBars title="NPC chat turns" daily={daily} field="chat_turns" unit="chat turns" />
                    <details>
                        <summary style={styles.summary}>Show as table</summary>
                        <Table
                            label="Daily numbers"
                            columns={[
                                { key: 'day', label: 'Day' },
                                { key: 'signups', label: 'Signups', numeric: true },
                                { key: 'active', label: 'Active', numeric: true },
                                { key: 'chat_turns', label: 'Chat turns', numeric: true },
                            ]}
                            rows={[...daily].reverse()}
                        />
                    </details>
                </>
            )}
        </Section>
    )
}

function RetentionSection({ id, report }) {
    return (
        <Section id={id} title="Retention" report={report}>
            {(retention) => (
                <>
                    <p style={styles.muted}>
                        Of players first seen at least N days ago, how many came back N or more days later.
                    </p>
                    <Table
                        label="Retention"
                        columns={[
                            { key: 'day', label: 'Back after', render: (r) => `D${r.day}+` },
                            { key: 'rate', label: 'Returned', numeric: true, render: (r) => share(r.returned, r.eligible) },
                            { key: 'of', label: 'Players', numeric: true, render: (r) => `${r.returned ?? MISSING} of ${r.eligible ?? MISSING}` },
                        ]}
                        rows={retention}
                    />
                </>
            )}
        </Section>
    )
}

function ProgressSection({ id, report }) {
    return (
        <Section id={id} title="Progress" report={report}>
            {(progress) => (
                <>
                    <SubTable title="Maps reached" columns={[{ key: 'map', label: 'Map' }, PLAYERS_COLUMN]} rows={progress.maps} />
                    <SubTable title="Story flags reached" columns={[{ key: 'flag', label: 'Flag' }, PLAYERS_COLUMN]} rows={progress.flags} />
                    <SubTable
                        title="Current levels (from autosaves)"
                        label="Current levels"
                        columns={[{ key: 'level', label: 'Level' }, PLAYERS_COLUMN]}
                        rows={progress.levels}
                    />
                    <SubTable
                        title={isNumber(progress.stalled_after_days)
                            ? `Stalled: autosave untouched ${progress.stalled_after_days}+ days, where it sits`
                            : 'Stalled: where autosaves sit'}
                        label="Stalled players"
                        columns={[{ key: 'map', label: 'Map' }, { key: 'room', label: 'Room (x, y)', render: roomLabel }, PLAYERS_COLUMN]}
                        rows={progress.stalled}
                    />
                </>
            )}
        </Section>
    )
}

function CombatSection({ id, report }) {
    return (
        <Section id={id} title="Combat" report={report}>
            {(combat) => (
                <Table
                    label="Combat by encounter"
                    columns={[
                        { key: 'encounter', label: 'Encounter' },
                        { key: 'starts', label: 'Fights', numeric: true },
                        { key: 'victories', label: 'Won', numeric: true },
                        { key: 'defeats', label: 'Died', numeric: true },
                        { key: 'death_rate', label: 'Death rate', numeric: true, render: (r) => share(r.defeats, r.starts) },
                        { key: 'flees', label: 'Fled', numeric: true },
                        { key: 'abandoned', label: 'Quit', numeric: true },
                        { key: 'avg_hp_pct_on_win', label: 'HP left on win', numeric: true, render: (r) => percent(r.avg_hp_pct_on_win) },
                        { key: 'avg_beats', label: 'Avg beats', numeric: true, render: (r) => oneDecimal(r.avg_beats) },
                        { key: 'avg_duration_s', label: 'Avg secs', numeric: true },
                    ]}
                    rows={combat}
                />
            )}
        </Section>
    )
}

function SessionsSection({ id, report }) {
    return (
        <Section id={id} title="Sessions" report={report}>
            {(sessions) => (
                <div style={styles.tiles}>
                    <Tile value={sessions.count} label="sessions" />
                    <Tile value={sessions.players} label="players" />
                    <Tile value={oneDecimal(sessions.median_minutes)} label="median minutes" />
                    <Tile value={oneDecimal(sessions.avg_minutes)} label="average minutes" />
                    <Tile value={oneDecimal(sessions.avg_minutes_per_player)} label="minutes per player" />
                </div>
            )}
        </Section>
    )
}

function NpcChatSection({ id, report }) {
    return (
        <Section id={id} title="NPC chat" report={report}>
            {(chat) => (
                <>
                    <div style={styles.tiles}>
                        <Tile value={chat.conversations} label="conversations" />
                        <Tile value={chat.turns} label="turns" />
                        <Tile value={chat.players} label="players" />
                        <Tile value={chat.avg_duration_s} label="avg secs / conversation" />
                        <Tile value={chat.avg_latency_ms} label="avg reply ms" />
                    </div>
                    <SubTable
                        title="By NPC"
                        label="NPC chat by NPC"
                        columns={[
                            { key: 'npc', label: 'NPC' },
                            { key: 'conversations', label: 'Convs', numeric: true },
                            { key: 'turns', label: 'Turns', numeric: true },
                            { key: 'avg_turns', label: 'Turns / conv', numeric: true },
                            { key: 'players', label: 'Players', numeric: true },
                            { key: 'avg_duration_s', label: 'Avg secs', numeric: true },
                        ]}
                        rows={chat.by_npc}
                    />
                </>
            )}
        </Section>
    )
}

// Each id is the report key the section reads; it is passed down, not repeated.
const SECTIONS = [
    ['players', PlayersSection], ['daily', DailySection], ['retention', RetentionSection],
    ['progress', ProgressSection], ['combat', CombatSection], ['sessions', SessionsSection],
    ['npc_chat', NpcChatSection],
]

export const SECTION_IDS = SECTIONS.map(([id]) => id)

// -- page --------------------------------------------------------------------

function PageShell({ children }) {
    return (
        <main style={styles.page}>
            <div style={styles.inner}>{children}</div>
        </main>
    )
}

export default function AdminAnalyticsPage() {
    const { report, days, selectDays, isLoading, error, notFound, isAdmin, reload } = useAdminAnalytics()

    const backLink = <Link to="/game" style={styles.link}>Back to the game</Link>

    if (notFound) {
        return (
            <PageShell>
                <p>Nothing here.</p>
                {backLink}
            </PageShell>
        )
    }

    // Until the server has confirmed an admin, a non-admin must not see what
    // this page is: nothing here names it or offers its controls, not even
    // when that first request fails.
    if (!isAdmin) {
        return (
            <PageShell>
                {error ? (
                    <ErrorRetry error={error} onRetry={reload} />
                ) : (
                    <p style={styles.muted}>Loading…</p>
                )}
            </PageShell>
        )
    }

    return (
        <PageShell>
            <header style={styles.header}>
                <h1 style={styles.title}>ANALYTICS</h1>
                <div style={styles.controls}>
                    {ANALYTICS_WINDOWS.map((w) => (
                        <button key={w} type="button" aria-pressed={days === w} onClick={() => selectDays(w)} style={styles.button(days === w)}>
                            {w} days
                        </button>
                    ))}
                    <button type="button" onClick={reload} disabled={isLoading} style={styles.button(false)}>
                        {isLoading ? 'Loading…' : 'Refresh'}
                    </button>
                    {backLink}
                </div>
            </header>

            {error && <ErrorRetry error={error} onRetry={reload} style={styles.errorBox} />}

            {!report && isLoading && <p style={styles.muted}>Loading analytics…</p>}

            {report && SECTIONS.map(([id, SectionView]) => <SectionView key={id} id={id} report={report} />)}
        </PageShell>
    )
}
