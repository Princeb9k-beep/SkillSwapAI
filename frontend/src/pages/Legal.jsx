// Public Privacy Policy + Terms of Service pages. Rendered for anyone (handled
// in the app Shell before the auth gate) so the links work signed-in or out.
//
// NOTE: this is plain-language starter content that reflects what the app does.
// Have it reviewed by a lawyer and set a real contact address before launch.

const UPDATED = "July 29, 2026";
const CONTACT = "support@skillswapai.app";

function Shell({ title, children }) {
  return (
    <section className="legal">
      <a className="btn btn-ghost legal-back" href="/">← Back to SkillSwap AI</a>
      <h1>{title}</h1>
      <p className="muted">Last updated: {UPDATED}</p>
      <div className="legal-body">{children}</div>
      <footer className="legal-foot muted">
        Questions? Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.
      </footer>
    </section>
  );
}

export function Privacy() {
  return (
    <Shell title="Privacy Policy">
      <p>
        This Privacy Policy explains what information SkillSwap AI ("we", "us")
        collects, how we use it, and the choices you have. By using the service you
        agree to this policy.
      </p>

      <h2>Information we collect</h2>
      <ul>
        <li><strong>Account info</strong> — your email, name, and password (stored only as a secure hash).</li>
        <li><strong>Profile & activity</strong> — the skills, goals, messages, sessions, and progress you create in the app.</li>
        <li><strong>Usage & device data</strong> — basic logs (pages, timestamps) and your time zone, used to run and improve the service.</li>
        <li><strong>If you sign in with Google or GitHub</strong>, we receive your name and verified email from that provider.</li>
      </ul>

      <h2>How we use it</h2>
      <ul>
        <li>To provide core features: matching, messaging, sessions, AI coaching, and progress tracking.</li>
        <li>To send you account and activity notifications (which you can control in Settings).</li>
        <li>To keep the service safe, prevent abuse, and comply with the law.</li>
      </ul>

      <h2>Service providers</h2>
      <p>
        We share limited data with processors that help us operate — for example an
        email provider (to send verification and notifications), an AI provider (to
        power the coach and other AI features), and hosting/infrastructure vendors.
        They may only use it to provide their service to us.
      </p>

      <h2>AI features</h2>
      <p>
        Text you submit to AI features (coach, scanner, translate, flashcards, etc.)
        is sent to our AI provider to generate a response. Don't paste sensitive
        personal data you wouldn't want processed this way.
      </p>

      <h2>Cookies & local storage</h2>
      <p>
        We use your browser's local storage to keep you signed in. We do not sell
        your data or use third-party advertising trackers.
      </p>

      <h2>Your choices</h2>
      <ul>
        <li>Update or correct your profile any time in Settings.</li>
        <li>Control notification and email preferences in Settings.</li>
        <li>Delete your account from Settings — this permanently removes your data.</li>
      </ul>

      <h2>Data retention & security</h2>
      <p>
        We keep your information while your account is active and delete it on request.
        We use reasonable technical safeguards, but no method of transmission or storage
        is 100% secure.
      </p>

      <h2>Children</h2>
      <p>The service isn't directed to children under 13 (or the minimum age in your country), and we don't knowingly collect their data.</p>

      <h2>Changes</h2>
      <p>We may update this policy; we'll change the "last updated" date above and, for material changes, notify you in the app.</p>
    </Shell>
  );
}

export function Terms() {
  return (
    <Shell title="Terms of Service">
      <p>
        These Terms govern your use of SkillSwap AI. By creating an account or using
        the service, you agree to them.
      </p>

      <h2>Your account</h2>
      <ul>
        <li>You must provide accurate information and keep your login secure.</li>
        <li>You're responsible for activity under your account.</li>
        <li>You must be old enough to form a binding contract in your country.</li>
      </ul>

      <h2>Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Harass, threaten, or harm other users, or post illegal, hateful, or infringing content.</li>
        <li>Spam, scam, or impersonate others; scrape or abuse the service or its AI features.</li>
        <li>Attempt to break, overload, or gain unauthorized access to the service.</li>
      </ul>
      <p>We may suspend or remove accounts that violate these Terms.</p>

      <h2>User content</h2>
      <p>
        You keep ownership of the content you post. You grant us a limited license to
        host and display it so we can operate the service. You're responsible for what
        you share and for your interactions with other users.
      </p>

      <h2>Skill swaps & sessions</h2>
      <p>
        SkillSwap AI helps people connect to teach and learn. We don't employ, vet, or
        guarantee any user, and we're not a party to arrangements between users. Meet
        and share information at your own discretion.
      </p>

      <h2>Paid plans & tokens</h2>
      <p>
        Some features require a paid plan or AI tokens. Pricing and inclusions are shown
        in the app and may change. Where payments are processed, they're handled by a
        third-party payment provider under their terms.
      </p>

      <h2>AI output</h2>
      <p>
        AI features can be wrong or incomplete. Treat AI output as guidance, not
        professional (legal, medical, financial) advice, and verify anything important.
      </p>

      <h2>Disclaimers & liability</h2>
      <p>
        The service is provided "as is" without warranties. To the extent permitted by
        law, we aren't liable for indirect or consequential damages arising from your
        use of the service.
      </p>

      <h2>Termination</h2>
      <p>You can stop using the service and delete your account any time. We may suspend or terminate access if you violate these Terms.</p>

      <h2>Changes</h2>
      <p>We may update these Terms; continued use after changes means you accept them.</p>
    </Shell>
  );
}
