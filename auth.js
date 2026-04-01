(function () {
  const API_BASE = '/api';

  async function apiRequest(path, options) {
    const response = await fetch(API_BASE + path, Object.assign({
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json'
      }
    }, options || {}));

    let payload = {};
    try {
      payload = await response.json();
    } catch (_err) {
      payload = {};
    }

    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: payload.error || 'Request failed.'
      };
    }

    return Object.assign({ ok: true }, payload);
  }

  async function getSession() {
    const result = await apiRequest('/auth/session', { method: 'GET' });
    if (!result.ok) return null;
    return result.session || null;
  }

  async function login(username, password) {
    return apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: username,
        password: password
      })
    });
  }

  async function logout() {
    await apiRequest('/auth/logout', { method: 'POST' });
    return { ok: true };
  }

  async function registerUser(username, password, email, mobile) {
    return apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username: username,
        password: password,
        email: email,
        mobile: mobile
      })
    });
  }

  async function requestPasswordReset(identifier) {
    return apiRequest('/auth/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({
        identifier: identifier
      })
    });
  }

  async function confirmPasswordReset(identifier, code, newPassword) {
    return apiRequest('/auth/password-reset/confirm', {
      method: 'POST',
      body: JSON.stringify({
        identifier: identifier,
        code: code,
        newPassword: newPassword
      })
    });
  }

  async function usernameExists(username) {
    const query = encodeURIComponent((username || '').trim());
    const result = await apiRequest('/users/exists?username=' + query, { method: 'GET' });
    if (!result.ok) return false;
    return !!result.exists;
  }

  async function requireSession(options) {
    const opts = Object.assign(
      {
        allowAdmin: true,
        allowLearner: true,
        redirectTo: 'login.html'
      },
      options || {}
    );

    const session = await getSession();
    if (!session) {
      window.location.replace(opts.redirectTo);
      return null;
    }

    const roleAllowed =
      (session.role === 'admin' && opts.allowAdmin) ||
      (session.role === 'learner' && opts.allowLearner);

    if (!roleAllowed) {
      window.location.replace(opts.redirectTo);
      return null;
    }

    return session;
  }

  async function readUserProgress(username) {
    const target = username ? '?username=' + encodeURIComponent(username) : '';
    const result = await apiRequest('/progress' + target, { method: 'GET' });
    if (!result.ok) return {};
    return result.progress || {};
  }

  async function writeUserProgress(username, progressMap) {
    const body = {
      username: username,
      progress: progressMap || {}
    };
    return apiRequest('/progress', {
      method: 'PUT',
      body: JSON.stringify(body)
    });
  }

  async function setPortalMeta(meta) {
    return apiRequest('/meta', {
      method: 'PUT',
      body: JSON.stringify({
        meta: meta || {}
      })
    });
  }

  async function getPortalMeta() {
    const result = await apiRequest('/meta', { method: 'GET' });
    if (!result.ok) return {};
    return result.meta || {};
  }

  async function getProgressSummary(totalLessons) {
    const query = '?totalLessons=' + encodeURIComponent(String(totalLessons || 0));
    const result = await apiRequest('/admin/summary' + query, { method: 'GET' });
    if (!result.ok) return [];
    return result.users || [];
  }

  async function deleteUser(username) {
    return apiRequest('/admin/users/' + encodeURIComponent(username || ''), {
      method: 'DELETE'
    });
  }

  window.RicsAuth = {
    login: login,
    logout: logout,
    registerUser: registerUser,
    requestPasswordReset: requestPasswordReset,
    confirmPasswordReset: confirmPasswordReset,
    usernameExists: usernameExists,
    getSession: getSession,
    requireSession: requireSession,
    readUserProgress: readUserProgress,
    writeUserProgress: writeUserProgress,
    getProgressSummary: getProgressSummary,
    deleteUser: deleteUser,
    setPortalMeta: setPortalMeta,
    getPortalMeta: getPortalMeta
  };
})();
