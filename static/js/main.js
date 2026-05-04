// ── Toast ───────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const toast   = document.getElementById('toast');
  const toastMsg  = document.getElementById('toastMsg');
  const toastIcon = document.getElementById('toastIcon');
  toastMsg.textContent  = msg;
  toastIcon.textContent = type === 'success' ? '✓' : '✕';
  toast.className = `toast ${type} show`;
  setTimeout(() => { toast.className = 'toast'; }, 3200);
}

// ── API helper ──────────────────────────────────────────────────────────
async function api(url, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res  = await fetch(url, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

// ── Skill chip toggle ───────────────────────────────────────────────────
function initSkillChips(containerId, hiddenInputId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll('.skill-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chip.classList.toggle('selected');
      updateHiddenSkills(containerId, hiddenInputId);
    });
  });
}

function updateHiddenSkills(containerId, hiddenInputId) {
  const chips    = document.querySelectorAll(`#${containerId} .skill-chip.selected`);
  const selected = [...chips].map(c => c.dataset.skill);
  const hidden   = document.getElementById(hiddenInputId);
  if (hidden) hidden.value = JSON.stringify(selected);
  return selected;
}

function getSelectedSkills(containerId) {
  const chips = document.querySelectorAll(`#${containerId} .skill-chip.selected`);
  return [...chips].map(c => c.dataset.skill);
}

// ── Set button loading state ────────────────────────────────────────────
function setLoading(btn, loading) {
  if (loading) {
    btn.dataset.orig = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span> Processing...';
    btn.disabled  = true;
  } else {
    btn.innerHTML = btn.dataset.orig || btn.innerHTML;
    btn.disabled  = false;
  }
}
