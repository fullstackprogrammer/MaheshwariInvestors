import { useState } from 'react';
import SiteLogo from './SiteLogo';

const HARDCODED_USER = 'mai108';
const HARDCODED_PASSWORD = 'admin$123';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    if (username.trim().toLowerCase() === HARDCODED_USER.toLowerCase() && password === HARDCODED_PASSWORD) {
      onLogin();
    } else {
      setError('Invalid username or password.');
    }
  };

  return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-dark-surface border border-dark-border rounded-xl shadow-xl pt-1 px-8 pb-8">
        <div className="flex flex-col items-center mb-5">
          <SiteLogo className="h-72 w-auto" />
        </div>
        <p className="text-dark-muted text-sm text-center mb-4">
          Sign in to view the dashboard
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-dark-muted mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-white placeholder-dark-muted focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter username"
              autoComplete="username"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-dark-muted mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-white placeholder-dark-muted focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </div>
          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}
          <button
            type="submit"
            className="w-full py-2.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors"
          >
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
