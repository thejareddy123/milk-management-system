
//  MILK MANAGEMENT SYSTEM - MAIN JS


//  SIDEBAR TOGGLE 
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
  });
  document.addEventListener('click', (e) => {
    if (window.innerWidth < 768 && !sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  });
}

//  DATE DISPLAY 
const dateEl = document.getElementById('topbarDate');
if (dateEl) {
  const now = new Date();
  dateEl.textContent = now.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
}

// AUTO FLASH DISMISS 
setTimeout(() => {
  document.querySelectorAll('.alert').forEach(el => {
    el.style.transition = 'opacity 0.4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 5000);

//  OTP INPUT BEHAVIOR 
const otpInputs = document.querySelectorAll('.otp-input');
otpInputs.forEach((input, i) => {
  input.addEventListener('input', (e) => {
    e.target.value = e.target.value.replace(/\D/g, '').slice(-1);
    if (e.target.value && i < otpInputs.length - 1) {
      otpInputs[i + 1].focus();
    }
    combineOTP();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !e.target.value && i > 0) {
      otpInputs[i - 1].focus();
    }
  });
  input.addEventListener('paste', (e) => {
    const paste = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
    otpInputs.forEach((inp, j) => {
      inp.value = paste[j] || '';
    });
    combineOTP();
    e.preventDefault();
  });
});

function combineOTP() {
  const combined = Array.from(otpInputs).map(i => i.value).join('');
  const hidden = document.getElementById('otpHidden');
  if (hidden) hidden.value = combined;
}

//  RESEND OTP 
const resendBtn = document.getElementById('resendOtpBtn');
let resendTimer;
function startResendCooldown(seconds = 30) {
  if (!resendBtn) return;
  resendBtn.disabled = true;
  let remaining = seconds;
  resendBtn.textContent = `Resend in ${remaining}s`;
  resendTimer = setInterval(() => {
    remaining--;
    resendBtn.textContent = `Resend in ${remaining}s`;
    if (remaining <= 0) {
      clearInterval(resendTimer);
      resendBtn.disabled = false;
      resendBtn.textContent = 'Resend OTP';
    }
  }, 1000);
}

if (resendBtn) {
  startResendCooldown(30);
  resendBtn.addEventListener('click', async () => {
    resendBtn.disabled = true;
    const res = await fetch('/resend-otp', { method: 'POST', headers: {'Content-Type': 'application/json'} });
    const data = await res.json();
    showToast(data.message, data.success ? 'success' : 'error');
    if (data.success) startResendCooldown(30);
    else { resendBtn.disabled = false; }
  });
}

//  MODAL HELPERS 
function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add('active'); document.body.style.overflow = 'hidden'; }
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove('active'); document.body.style.overflow = ''; }
}
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) { overlay.classList.remove('active'); document.body.style.overflow = ''; }
  });
});

//  TOAST 
function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `alert alert-${type}`;
  t.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;min-width:280px;max-width:380px;box-shadow:0 8px 32px rgba(0,0,0,0.15);';
  t.innerHTML = `<span>${msg}</span><button onclick="this.parentElement.remove()" class="alert-close">×</button>`;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; t.style.transition='opacity 0.4s'; setTimeout(()=>t.remove(),400); }, 4000);
}

// MILK ENTRY: AUTO PRICE LOOKUP 
const fatInput  = document.getElementById('fatInput');
const snfInput  = document.getElementById('snfInput');
const pricePreview = document.getElementById('pricePreview');

async function lookupRate() {
  const fat = parseFloat(fatInput?.value);
  const snf = parseFloat(snfInput?.value);
  if (!fatInput || !snfInput || isNaN(fat) || isNaN(snf) || fat <= 0 || snf <= 0) {
    if (pricePreview) pricePreview.classList.remove('show');
    return;
  }
  try {
    const res = await fetch(`/supplier/api/lookup-rate?fat=${fat}&snf=${snf}`);
    const data = await res.json();
    if (data.success && pricePreview) {
      pricePreview.classList.add('show');
      pricePreview.querySelector('.price-value').textContent = `₹${parseFloat(data.rate).toFixed(2)}/L`;
      pricePreview.querySelector('.fat-range').textContent = data.fat_range;
      pricePreview.querySelector('.snf-range').textContent = data.snf_range;
      document.getElementById('rateIdInput').value = data.rate_id;
      updateTotal();
    } else if (pricePreview) {
      pricePreview.classList.remove('show');
      document.getElementById('rateIdInput').value = '';
    }
  } catch(e) {}
}

function updateTotal() {
  const qty = parseFloat(document.getElementById('qtyInput')?.value);
  const priceText = pricePreview?.querySelector('.price-value')?.textContent;
  if (!qty || !priceText || !pricePreview?.classList.contains('show')) return;
  const price = parseFloat(priceText.replace('₹', '').replace('/L', ''));
  const total = qty * price;
  const totalEl = document.getElementById('totalPreview');
  if (totalEl) totalEl.textContent = `Total: ₹${total.toFixed(2)}`;
}

if (fatInput) fatInput.addEventListener('input', lookupRate);
if (snfInput) snfInput.addEventListener('input', lookupRate);
document.getElementById('qtyInput')?.addEventListener('input', updateTotal);

// MILK ENTRY FORM SUBMIT 
const milkEntryForm = document.getElementById('milkEntryForm');
if (milkEntryForm) {
  milkEntryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = milkEntryForm.querySelector('[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Saving...';
    const formData = new FormData(milkEntryForm);
    const res = await fetch('/supplier/milk-entry', { method: 'POST', body: formData });
    const data = await res.json();
    showToast(data.message, data.success ? 'success' : 'error');
    if (data.success) {
      milkEntryForm.reset();
      if (pricePreview) pricePreview.classList.remove('show');
      loadRecentEntries?.();
    }
    btn.disabled = false;
    btn.textContent = 'Save Entry';
  });
}

//  CONFIRM DELETE/REJECT 
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', (e) => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

//  PASSWORD STRENGTH
const pwInput = document.getElementById('passwordInput');
const pwStrength = document.getElementById('pwStrength');
if (pwInput && pwStrength) {
  pwInput.addEventListener('input', () => {
    const pw = pwInput.value;
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[a-z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^a-zA-Z0-9]/.test(pw)) score++;
    const labels = ['', 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const colors = ['', '#ef4444','#f59e0b','#eab308','#22c55e','#15803d'];
    pwStrength.textContent = labels[score] || '';
    pwStrength.style.color = colors[score];
  });
}

//  ACTIVE NAV 
const currentPath = window.location.pathname;
document.querySelectorAll('.nav-item').forEach(link => {
  if (link.getAttribute('href') === currentPath) {
    link.classList.add('active');
  }
});
