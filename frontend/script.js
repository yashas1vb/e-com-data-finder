/* ============================================================
   E-Com Data Finder — SPA Script
   ============================================================ */

const API_BASE_URL = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || 'http://localhost:5000';

// ──────────────────────────────────────────────
// THEME TOGGLE
// ──────────────────────────────────────────────
const themeToggleBtn = document.getElementById('themeToggle');
const html = document.documentElement;

function applyTheme(theme) {
  html.setAttribute('data-theme', theme);
  themeToggleBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
  localStorage.setItem('theme', theme);
}

themeToggleBtn.addEventListener('click', () => {
  const current = html.getAttribute('data-theme');
  applyTheme(current === 'dark' ? 'light' : 'dark');
});

// Load saved theme
applyTheme(localStorage.getItem('theme') || 'dark');

// ──────────────────────────────────────────────
// SPA NAVIGATION
// ──────────────────────────────────────────────
const pages = ['home', 'discovery', 'filters', 'emails'];
const navIds = {
  home: 'nav-home',
  discovery: 'nav-discovery',
  filters: 'nav-filters',
  emails: 'nav-emails'
};

function goTo(page) {
  pages.forEach(p => {
    const el = document.getElementById('page-' + p);
    const btn = document.getElementById(navIds[p]);
    if (p === page) {
      el.classList.add('active');
      btn.classList.add('active');
    } else {
      el.classList.remove('active');
      btn.classList.remove('active');
    }
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ──────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ──────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icons = { error: '❌', success: '✅', info: 'ℹ️' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.4s'; setTimeout(() => toast.remove(), 400); }, 4000);
}

function showError(msg) { showToast(msg, 'error'); }
function showSuccess(msg) { showToast(msg, 'success'); }

// ──────────────────────────────────────────────
// CSV HELPERS
// ──────────────────────────────────────────────
function parseCSVRow(text) {
  const result = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') { inQuotes = !inQuotes; }
    else if (char === ',' && !inQuotes) { result.push(current.trim()); current = ''; }
    else { current += char; }
  }
  result.push(current.trim());
  return result;
}

function buildTable(csvText) {
  const rows = csvText.split('\n').filter(r => r.trim() !== '');
  if (rows.length === 0) return null;
  const headers = parseCSVRow(rows[0]);
  const dataRows = rows.slice(1).map(parseCSVRow);

  let html = '<table class="csv-table"><thead><tr>';
  headers.forEach(h => { html += `<th>${h}</th>`; });
  html += '</tr></thead><tbody>';
  dataRows.forEach(row => {
    html += '<tr>' + row.map(cell => `<td>${cell}</td>`).join('') + '</tr>';
  });
  html += '</tbody></table>';
  return html;
}

async function renderResults({ sectionId, tableId, downloadBtnId, filePath, downloadName }) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/download?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) throw new Error('Failed to fetch file');
    const blob = await res.blob();
    const text = await blob.text();
    const tableHtml = buildTable(text);
    if (!tableHtml) throw new Error('CSV is empty');

    document.getElementById(tableId).innerHTML = tableHtml;
    document.getElementById(sectionId).classList.add('visible');

    const dlBtn = document.getElementById(downloadBtnId);
    dlBtn.onclick = () => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = downloadName;
      document.body.appendChild(a); a.click();
      URL.revokeObjectURL(url); a.remove();
    };
  } catch (err) {
    showError(err.message || 'Failed to load results');
    throw err;
  }
}

// ──────────────────────────────────────────────
// SITE DISCOVERY
// ──────────────────────────────────────────────
async function handleFetchSites() {
  const btn = document.getElementById('fetchBtn');
  const country = document.getElementById('country').value;
  const city = document.getElementById('state').value;
  const keyword = document.getElementById('industry').value;
  const count = document.getElementById('count').value;

  if (!country || !city || !keyword) { showError('Please fill Country, State/City, and Industry fields.'); return; }
  if (count < 1 || count > 1000) { showError('Count must be between 1 and 1000.'); return; }

  btn.disabled = true;
  btn.textContent = 'Processing, please wait…';

  try {
    const res = await fetch(`${API_BASE_URL}/api/fetch-sites`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ country, city, keyword, count: parseInt(count) })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to fetch sites');
    if (data.status === 'success') {
      showSuccess('Sites fetched successfully!');
      await renderResults({ sectionId: 'discoveryResults', tableId: 'discoveryTable', downloadBtnId: 'discoveryDownloadBtn', filePath: data.file, downloadName: 'Websites_Fetched.csv' });
    } else { throw new Error(data.error || 'Failed to fetch sites'); }
  } catch (err) { showError(err.message || 'Error fetching sites.'); }
  finally { btn.disabled = false; btn.textContent = 'Fetch Sites'; }
}

// ──────────────────────────────────────────────
// FILTERS
// ──────────────────────────────────────────────
function updateFilterSelection() {
  document.querySelectorAll('.filter-option').forEach(el => el.classList.remove('selected'));
  const checked = document.querySelector('input[name="filterChoice"]:checked');
  if (checked) { checked.closest('.filter-option').classList.add('selected'); }
}

async function handleApplyFilters() {
  const btn = document.getElementById('applyFiltersBtn');
  const checked = document.querySelector('input[name="filterChoice"]:checked');
  if (!checked) { showError('Please select a filter option.'); return; }

  const excludeFile = document.getElementById('excludeCSV').files[0];
  if (!excludeFile) { showError('Please upload a CSV file to filter.'); return; }

  btn.disabled = true;
  btn.textContent = 'Processing…';

  try {
    const formData = new FormData();
    formData.append('file', excludeFile);
    formData.append('filters', checked.value);

    const res = await fetch(`${API_BASE_URL}/api/filter-sites`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to apply filters');
    if (data.status === 'success') {
      showSuccess('Filters applied successfully!');
      await renderResults({ sectionId: 'filterResults', tableId: 'filterTable', downloadBtnId: 'filterDownloadBtn', filePath: data.file, downloadName: 'Websites_Filtered.csv' });
    } else { throw new Error(data.error || 'Failed to apply filters'); }
  } catch (err) { showError(err.message || 'Error applying filters.'); }
  finally { btn.disabled = false; btn.textContent = 'Apply Filters'; }
}

// ──────────────────────────────────────────────
// EMAIL EXTRACTOR
// ──────────────────────────────────────────────
function handleEmailFileSelect(input) {
  const dropZone = document.getElementById('emailDropZone');
  if (input.files && input.files[0]) {
    const fname = input.files[0].name;
    dropZone.querySelector('.dz-text').innerHTML = `<span class="dz-browse">📄 ${fname}</span>`;
  }
}

// Drag and drop
const emailDropZone = document.getElementById('emailDropZone');
const csvFileInput = document.getElementById('csvFile');

emailDropZone.addEventListener('dragover', (e) => { e.preventDefault(); emailDropZone.classList.add('active'); });
emailDropZone.addEventListener('dragleave', () => emailDropZone.classList.remove('active'));
emailDropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  emailDropZone.classList.remove('active');
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    const dt = new DataTransfer();
    dt.items.add(files[0]);
    csvFileInput.files = dt.files;
    handleEmailFileSelect(csvFileInput);
  }
});

async function handleFetchEmails() {
  const btn = document.getElementById('fetchEmailBtn');
  const file = csvFileInput.files[0];
  if (!file) { showError('Please upload a CSV file.'); return; }

  btn.disabled = true;
  btn.textContent = 'Processing…';

  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE_URL}/api/fetch-emails`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to fetch emails');
    if (data.status === 'success' && data.file) {
      showSuccess('Emails extracted successfully!');
      await renderResults({ sectionId: 'emailResults', tableId: 'emailTable', downloadBtnId: 'emailDownloadBtn', filePath: data.file, downloadName: 'Emails_Extracted.csv' });
    } else { throw new Error('No file received from server'); }
  } catch (err) { showError(err.message || 'Error extracting emails.'); }
  finally { btn.disabled = false; btn.textContent = 'Fetch Email IDs'; }
}
