import { readApiJson } from '../api-response.js'
import BrandLogo from '../components/BrandLogo.jsx';
import { ArrowRight, BookOpen, Check, Languages, LogOut, Settings, ShieldCheck, UserRound } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { authHeaders, canAccessWorkspace, clearRole, getProfile, isAdmin, setActiveChannel, setProfile } from '../auth.js';
import './signin.css';
import './choose-workspace.css';

const steps = [
  { title: 'Bring your draft', text: 'Paste a few lines or upload your brief.' },
  { title: 'Make it your own', text: 'Choose a format and add what matters.' },
  { title: 'Give it the final touch', text: 'Review, edit and share with confidence.' },
];

export default function ChooseWorkspace() {
  const navigate = useNavigate();
  const [profile, updateProfile] = useState(getProfile());
  useEffect(() => {
    fetch('/api/access/me', { headers: authHeaders() }).then(async (response) => {
      if (!response.ok) return;
      const fresh = await readApiJson(response);
      const previous = getProfile()?.active_channel_id;
      if (fresh.channels.some((channel) => channel.id === previous)) fresh.active_channel_id = previous;
      setProfile(fresh);
      updateProfile(fresh);
    }).catch(() => {});
  }, []);


  return (
    <div className="workspace-screen harf-welcome">
      <header className="workspace-header welcome-header">
        <div className="workspace-header-top">
          <button className="welcome-signout" type="button" onClick={() => { clearRole(); navigate('/'); }}><LogOut size={16} /><span>Sign out</span></button>
          <div className="workspace-header-actions">
          <button className="workspace-admin-button" type="button" onClick={() => navigate('/activity')}>My activity & requests</button>
          {isAdmin() && <button className="workspace-admin-button" type="button" onClick={() => navigate(`/admin/${profile?.active_channel_id || ''}`)}><Settings size={15} /> {profile?.role === 'approval_admin' ? 'Review approvals' : 'Administration'}</button>}
            <button className="workspace-profile-button" type="button" popoverTarget="workspace-profile" aria-label="Open your profile" title="Your profile"><UserRound size={21} /></button>
          </div>
        </div>
        <div className="welcome-banner-copy">
          <h1 id="welcome-title">Welcome to <BrandLogo /></h1>
          <p>AI-powered copy for etisalat’s digital experiences.</p>
        </div>
      </header>
      <div id="workspace-profile" popover="auto" className="workspace-profile-panel" aria-label="Your profile">
        <div className="workspace-profile-heading"><UserRound size={24} /><strong>{profile?.name || 'Your profile'}</strong></div>
        <p className="workspace-profile-email">{profile?.email}</p>
        <dl><div><dt>Role</dt><dd>{({ user: 'User', approval_admin: 'Reviewer', channel_admin: 'Administrator', super_admin: 'Super admin' })[profile?.role] || 'User'}</dd></div>{profile?.role === 'super_admin' && <div><dt>Team channel</dt><dd>{profile?.channels?.find((item) => item.id === profile.active_channel_id)?.name || 'No channel'}</dd></div>}</dl>
        {profile?.role === 'super_admin' && <label className="workspace-profile-channel">Switch team channel<select value={profile.active_channel_id || ''} onChange={(event) => { setActiveChannel(event.target.value); window.location.reload(); }}>{profile.channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label>}
      </div>
      <main id="welcome-main" className="welcome-main">
        <section className="welcome-introduction" aria-labelledby="welcome-intro-title">
          <div className="welcome-intro-content">
          <h2 id="welcome-intro-title">Make your content count.</h2>
          <p>Turn a rough draft into polished writing, with your writing guidelines built in.</p>
          <div className="welcome-start-actions">
          {canAccessWorkspace('rewrite') ? <Link className="welcome-primary" to="/copywriter">Start Rewriting <ArrowRight size={17} /></Link> : <p className="welcome-no-access" role="status">Ask your administrator to enable Harf access for your account.</p>}
          <button className="welcome-tutorial" type="button" onClick={() => window.dispatchEvent(new CustomEvent('rewrite:open-tutorial'))}><BookOpen size={16} /> Take a quick tour</button>
          </div>
          </div>
        </section>
        <div className="welcome-reassurance"><span><Languages size={16} aria-hidden="true" /> English & Arabic</span><span><ShieldCheck size={16} aria-hidden="true" /> Your writing guidelines</span><span><Check size={16} aria-hidden="true" /> You have the final say</span></div>
        <section className="welcome-how" aria-labelledby="welcome-how-title">
          <h2 id="welcome-how-title">Simple from start to finish.</h2>
          <ol className="welcome-steps">{steps.map(({ title, text }, index) => <li key={title}><span className="welcome-step-number">{index + 1}</span><div><h3>{title}</h3><p>{text}</p></div></li>)}</ol>
        </section>
      </main>
      <footer className="welcome-footer"><strong>Created by the AI Engineering and Factory Team</strong><p>Need help? Contact your administrator.</p><p className="welcome-disclaimer">AI-generated content. Review important information before sharing or publishing.</p></footer>
    </div>
  );
}
