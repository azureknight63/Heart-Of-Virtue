import { useState } from 'react'
import BaseDialog from './BaseDialog'
import { colors, spacing } from '../styles/theme'
import GameText from './GameText'
import GameButton from './GameButton'

const EFFECTIVE_DATE = 'March 26, 2026'

function Section({ title, children }) {
    return (
        <div style={{ marginBottom: spacing.xl }}>
            <GameText
                variant="primary"
                size="sm"
                weight="bold"
                style={{ textTransform: 'uppercase', letterSpacing: '1px', marginBottom: spacing.sm, display: 'block' }}
            >
                {title}
            </GameText>
            <div style={{ color: colors.text.main, fontSize: '13px', lineHeight: '1.7', fontFamily: 'monospace' }}>
                {children}
            </div>
        </div>
    )
}

function TermsContent() {
    return (
        <div>
            <GameText variant="dim" size="xs" style={{ display: 'block', marginBottom: spacing.xl, fontFamily: 'monospace' }}>
                Effective Date: {EFFECTIVE_DATE}
            </GameText>

            <Section title="1. Acceptance">
                By creating an account or playing Heart of Virtue, you agree to these Terms of Service
                and the Privacy Policy below. If you do not agree, do not create an account.
            </Section>

            <Section title="2. Who Can Play">
                Heart of Virtue is open to players of all ages. If you are under 13, you need a
                parent or guardian's permission before creating an account, as registration requires
                providing personal information (email address).
            </Section>

            <Section title="3. Your Account">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}>You must provide a valid username and email address at registration. Your email is used only for account recovery.</li>
                    <li style={{ marginBottom: spacing.xs }}>You are responsible for keeping your password secure. We cannot recover your password — only reset it via your email.</li>
                    <li style={{ marginBottom: spacing.xs }}>Passwords are stored using Argon2id hashing. We never store or see your plain-text password.</li>
                    <li>One account per person.</li>
                </ul>
            </Section>

            <Section title="4. What You Can Do">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}>Play Heart of Virtue for personal, non-commercial enjoyment.</li>
                    <li>Access premium content (later chapters) once paid features become available.</li>
                </ul>
            </Section>

            <Section title="5. What You Cannot Do">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}>Reverse-engineer, copy, or redistribute the game, its code, or its story content.</li>
                    <li style={{ marginBottom: spacing.xs }}>Attempt to access or interfere with other players' accounts or data.</li>
                    <li style={{ marginBottom: spacing.xs }}>Use the game for any commercial purpose.</li>
                    <li>Automate or bot gameplay in ways that harm the service.</li>
                </ul>
            </Section>

            <Section title="6. Payments (Coming Soon)">
                Heart of Virtue uses a freemium model. The base game is free. Later chapters will
                require a one-time purchase or subscription — exact terms, pricing, and refund
                policy will be described at the point of sale when those features launch.
            </Section>

            <Section title="7. AI-Powered Features">
                Certain in-game features — including NPC ambient behavior — are powered by
                third-party AI services (OpenAI / OpenRouter). To make these features work, your
                game state, character data, and messages sent to in-game characters may be
                transmitted to those services. This data is used only to generate the in-game
                response and is not used for advertising. See the Privacy Policy for more detail.
            </Section>

            <Section title="8. Intellectual Property">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}>Game code is licensed under the PolyForm Noncommercial License.</li>
                    <li style={{ marginBottom: spacing.xs }}>Story, lore, characters, and assets are licensed under CC BY-NC-ND 4.0.</li>
                    <li>You may not reproduce or distribute story or asset content without explicit permission.</li>
                </ul>
            </Section>

            <Section title="9. Account Deletion & Termination">
                You can delete your account at any time from within the game without needing to
                contact us. Deletion removes your account and associated data permanently. We may
                also suspend or terminate accounts that violate these terms.
            </Section>

            <Section title="10. Disclaimer of Warranties">
                Heart of Virtue is provided "as is" without warranties of any kind. We make no
                guarantees about uptime, data preservation, or feature availability.
            </Section>

            <Section title="11. Limitation of Liability">
                To the fullest extent permitted by US law, the developer is not liable for any
                indirect, incidental, special, or consequential damages arising from your use of
                the game.
            </Section>

            <Section title="12. Governing Law">
                These terms are governed by the laws of the United States. Any disputes will be
                resolved in US courts.
            </Section>

            <Section title="13. Changes to These Terms">
                We may update these terms from time to time. If you have opted in to email
                updates, we will notify you. Continued use of the game after changes take effect
                constitutes acceptance.
            </Section>

            <Section title="14. Contact">
                Questions or concerns? Reach us at:{' '}
                <span style={{ color: colors.accent }}>asregbert@gmail.com</span>
            </Section>
        </div>
    )
}

function PrivacyContent() {
    return (
        <div>
            <GameText variant="dim" size="xs" style={{ display: 'block', marginBottom: spacing.xl, fontFamily: 'monospace' }}>
                Effective Date: {EFFECTIVE_DATE}
            </GameText>

            <Section title="What We Collect">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}><strong style={{ color: colors.text.highlight }}>Username</strong> — required to identify your account.</li>
                    <li style={{ marginBottom: spacing.xs }}><strong style={{ color: colors.text.highlight }}>Email address</strong> — required at registration for account recovery. Stored encrypted.</li>
                    <li style={{ marginBottom: spacing.xs }}><strong style={{ color: colors.text.highlight }}>Password hash</strong> — we store only an Argon2id hash. Your actual password is never stored or readable by us.</li>
                    <li style={{ marginBottom: spacing.xs }}><strong style={{ color: colors.text.highlight }}>Game save data</strong> — character stats, inventory, and story progress stored in our database to keep your game persistent across sessions.</li>
                    <li><strong style={{ color: colors.text.highlight }}>Email opt-in</strong> — if you choose to receive updates or newsletters, we store your preference. You can withdraw it at any time.</li>
                </ul>
            </Section>

            <Section title="How We Use Your Data">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}>To run your account and persist your game progress.</li>
                    <li style={{ marginBottom: spacing.xs }}>To send account recovery emails when you request them.</li>
                    <li style={{ marginBottom: spacing.xs }}>To send updates or newsletters if you opted in.</li>
                    <li>To power AI-driven in-game features (see below).</li>
                </ul>
            </Section>

            <Section title="AI Processing">
                Some in-game features (such as NPC behavior) send data to OpenAI / OpenRouter, a
                third-party AI service. This data may include your game state, character data, and
                messages you send to in-game characters. It is used only to generate the immediate
                in-game response and is not used to train AI models or for advertising.
                <br /><br />
                OpenAI's privacy policy applies to data processed through their service:
                <span style={{ color: colors.text.muted }}> openai.com/policies/privacy-policy</span>
            </Section>

            <Section title="Analytics">
                We plan to add anonymous, aggregate analytics to understand how the game is
                played. This will not collect or transmit any personally identifiable information.
                We will update this policy before enabling analytics.
            </Section>

            <Section title="Email Communications">
                Your email address is used only for account recovery unless you explicitly opt in
                to updates. We do not share your email with third parties or advertisers. You can
                unsubscribe from optional emails at any time from your account settings.
            </Section>

            <Section title="Your Rights & Control">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}>You can update or remove your email address from your account settings at any time — no request needed.</li>
                    <li style={{ marginBottom: spacing.xs }}>You can delete your entire account from within the game at any time. This permanently removes your account and all associated data.</li>
                    <li>We do not sell your data. Ever.</li>
                </ul>
            </Section>

            <Section title="Data Security">
                Passwords are hashed with Argon2id (a leading password hashing algorithm). Email
                addresses are stored encrypted. Game save data is stored in a managed cloud
                database (Turso / LibSQL).
            </Section>

            <Section title="Third-Party Services">
                <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                    <li style={{ marginBottom: spacing.xs }}><strong style={{ color: colors.text.highlight }}>Turso (LibSQL)</strong> — cloud database for account and save data.</li>
                    <li>
                        <strong style={{ color: colors.text.highlight }}>OpenAI / OpenRouter</strong> — AI inference for in-game features. Game state
                        and in-game messages may be sent to these services.
                    </li>
                </ul>
                <br />
                No data is sold to, or shared with, advertisers or data brokers.
            </Section>

            <Section title="Children">
                We welcome players of all ages. If you are under 13, please get a parent or
                guardian's permission before creating an account, as registration requires
                providing an email address.
            </Section>

            <Section title="Changes to This Policy">
                If we make significant changes to how we collect or use data, we will notify
                opted-in users by email and post notice in the game before the changes take effect.
            </Section>

            <Section title="Contact">
                Privacy questions or data requests:{' '}
                <span style={{ color: colors.accent }}>asregbert@gmail.com</span>
            </Section>
        </div>
    )
}

export default function TermsOfServiceModal({ onClose }) {
    const [activeTab, setActiveTab] = useState('tos')

    const tabStyle = (tab) => ({
        flex: 1,
        padding: `${spacing.sm} ${spacing.md}`,
        background: activeTab === tab ? colors.bg.terminal : 'none',
        border: 'none',
        borderBottom: `2px solid ${activeTab === tab ? colors.primary : 'transparent'}`,
        color: activeTab === tab ? colors.primary : colors.text.muted,
        cursor: 'pointer',
        fontFamily: 'monospace',
        fontSize: '13px',
        fontWeight: activeTab === tab ? 'bold' : 'normal',
        textTransform: 'uppercase',
        letterSpacing: '1px',
        transition: 'color 0.2s, border-color 0.2s, background 0.2s',
    })

    return (
        <BaseDialog
            title="Terms & Privacy"
            onClose={onClose}
            maxWidth="640px"
            width="92%"
            zIndex={1100}
        >
            {/* Tabs */}
            <div style={{ display: 'flex', marginBottom: spacing.lg, borderBottom: `1px solid ${colors.border.light}` }}>
                <button
                    style={tabStyle('tos')}
                    onClick={() => setActiveTab('tos')}
                    aria-selected={activeTab === 'tos'}
                    role="tab"
                >
                    Terms of Service
                </button>
                <button
                    style={tabStyle('privacy')}
                    onClick={() => setActiveTab('privacy')}
                    aria-selected={activeTab === 'privacy'}
                    role="tab"
                >
                    Privacy Policy
                </button>
            </div>

            {/* Content */}
            <div style={{ overflowY: 'auto', flex: 1, paddingRight: spacing.xs }}>
                {activeTab === 'tos' ? <TermsContent /> : <PrivacyContent />}
            </div>

            {/* Footer */}
            <div style={{ marginTop: spacing.lg, borderTop: `1px solid ${colors.border.light}`, paddingTop: spacing.lg, textAlign: 'center' }}>
                <GameButton variant="secondary" onClick={onClose} size="small">
                    Close
                </GameButton>
            </div>
        </BaseDialog>
    )
}
