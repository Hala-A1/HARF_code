import { readApiJson } from '../api-response.js'
import HarfLogo from '../components/HarfLogo.jsx'
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { setProfile } from '../auth.js';
import './signin.css';

export default function SignIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [keepSignedIn, setKeepSignedIn] = useState(true);

  const [error, setError] = useState('');
  const [signingIn, setSigningIn] = useState(false);

  async function handleSignIn(e) {
    e.preventDefault();
    setSigningIn(true);
    setError('');
    try {
      const response = await fetch('/api/access/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email.trim(), password }),
      });
      const profile = await readApiJson(response);
      if (!response.ok) throw new Error(profile.detail || 'Could not sign in.');
      setProfile(profile);
      navigate('/choose');
    } catch (requestError) {
      setError(requestError.message || 'Could not sign in.');
    } finally {
      setSigningIn(false);
    }
  }

  return (
    <div className="signin-screen">
      <div className="signin-header">
        <div className="signin-banner-content">
          <div className="signin-brand-stack">
            <div className="brand-mark"><HarfLogo /></div>
          </div>
          <div className="signin-copy">
          <h1>Create, enhance, and scale content.</h1>
          </div>
        </div>

        <div className="signin-foot">© 2026 Etisalat · Internal tool · Harf</div>
      </div>

      <div className="signin-form-wrap">
        <form className="signin-form" onSubmit={handleSignIn}>
          <p className="kicker">WELCOME</p>
          <h2>Sign in to Harf</h2>

          <div className="field">
            <label htmlFor="email">Username</label>
            <input
              id="email"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <div className="form-row-between">
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={keepSignedIn}
                onChange={(e) => setKeepSignedIn(e.target.checked)}
              />
              Keep me signed in
            </label>
          </div>

          {error && <p className="signin-error" role="alert">{error}</p>}
          <button className="btn-primary" type="submit" disabled={signingIn}>{signingIn ? 'Signing in…' : 'Sign in with SSO'}</button>

          <p className="signup-note">Use your corporate credentials to sign in.<br />Contact IT support if you have issues.</p>
        </form>
      </div>
    </div>
  );
}
