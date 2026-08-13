document.addEventListener('DOMContentLoaded', () => {
    // ─── Docs Code Tab Switcher ───
    const codeTabs = document.querySelectorAll('[data-tab]');
    const codeDisplay = document.getElementById('code-display');

    const codeTemplates = {
        python: `import requests

url = "http://localhost:5000/api/check"
headers = {
    "X-API-Key": "YOUR_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "url": "https://checkout.stripe.com/c/pay/cs_live_...",
    "card": "4532010000000000|12|29|123"
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())`,
        nodejs: `const axios = require('axios');

const url = 'http://localhost:5000/api/check';
const headers = {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
};
const data = {
    url: 'https://checkout.stripe.com/c/pay/cs_live_...',
    card: '4532010000000000|12|29|123'
};

axios.post(url, data, { headers })
    .then(res => console.log(res.data))
    .catch(err => console.error(err.response.data));`,
        curl: `curl -X POST http://localhost:5000/api/check \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://checkout.stripe.com/c/pay/cs_live_...",
    "card": "4532010000000000|12|29|123"
  }'`
    };

    codeTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            codeTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const lang = tab.getAttribute('data-tab');
            codeDisplay.textContent = codeTemplates[lang];
        });
    });

    // Set initial python code
    if (codeDisplay) {
        codeDisplay.textContent = codeTemplates.python;
    }


    // ─── BIN Lookup Tool ───
    const binForm = document.getElementById('bin-form');
    const binInput = document.getElementById('bin-input');
    const binBtn = document.getElementById('bin-btn');
    const binLoader = document.getElementById('bin-loader');
    const binResult = document.getElementById('bin-result');

    if (binForm) {
        binForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const bin = binInput.value.trim().replace(/\D/g, '');
            if (bin.length < 6) {
                alert('Please enter at least 6 digits.');
                return;
            }

            binBtn.disabled = true;
            binLoader.classList.remove('hidden');
            binResult.classList.add('hidden');

            try {
                const res = await fetch(`/api/bin/${bin}`);
                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.error || 'Failed to fetch BIN details.');
                }

                document.getElementById('res-bin').textContent = data.bin || bin.substring(0, 6);
                document.getElementById('res-brand').textContent = (data.brand || 'Unknown').toUpperCase();
                document.getElementById('res-type').textContent = (data.type || 'Unknown').toUpperCase();
                document.getElementById('res-category').textContent = (data.category || 'Unknown').toUpperCase();
                document.getElementById('res-bank').textContent = data.bank || 'Unknown';
                document.getElementById('res-country').textContent = `${data.flag || ''} ${data.country_name || 'Unknown'}`;

                binResult.classList.remove('hidden');
            } catch (err) {
                alert(err.message);
            } finally {
                binBtn.disabled = false;
                binLoader.classList.add('hidden');
            }
        });
    }


    // ─── Developer Stats Dashboard ───
    const keyForm = document.getElementById('key-form');
    const keyInput = document.getElementById('key-input');
    const keyBtn = document.getElementById('key-btn');
    const keyLoader = document.getElementById('key-loader');
    const dashboardResult = document.getElementById('dashboard-result');

    if (keyForm) {
        keyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const key = keyInput.value.trim();
            if (!key) {
                alert('Please enter your API Key.');
                return;
            }

            keyBtn.disabled = true;
            keyLoader.classList.remove('hidden');
            dashboardResult.classList.add('hidden');

            try {
                const res = await fetch('/api/stats', {
                    headers: {
                        'X-API-Key': key
                    }
                });
                const data = await res.json();

                if (!res.ok) {
                    throw new Error(data.error || 'Invalid API Key or unauthorized request.');
                }

                const statusBadge = document.getElementById('dash-status');
                statusBadge.textContent = 'Active';
                statusBadge.className = 'badge badge-active';

                document.getElementById('dash-plan').textContent = data.plan_type;
                
                const limit = data.hits_per_day;
                document.getElementById('dash-quota').textContent = `${data.daily_count} / ${limit > 0 ? limit : 'Unlimited'}`;
                document.getElementById('dash-total').textContent = data.total_count;

                const dateObj = new Date(data.created_at);
                document.getElementById('dash-created').textContent = dateObj.toLocaleDateString();

                dashboardResult.classList.remove('hidden');
            } catch (err) {
                alert(err.message);
            } finally {
                keyBtn.disabled = false;
                keyLoader.classList.add('hidden');
            }
        });
    }

    // ─── Telegram Mini App Logic ───
    const tg = window.Telegram ? window.Telegram.WebApp : null;
    
    // Check if we are inside Telegram or testing with ?mock=1
    const urlParams = new URLSearchParams(window.location.search);
    const isMock = urlParams.get('mock') || urlParams.get('tgWebAppStartParam') === 'mock';
    
    if ((tg && tg.initData) || isMock) {
        document.body.classList.add('telegram-mode');
        if (tg) {
            tg.ready();
            tg.expand();
        }
        
        // Mock initData if requested
        const initData = tg && tg.initData ? tg.initData : (isMock === 'admin' ? 'mock_admin' : 'mock_user');
        
        // Elements
        const miniUserName = document.getElementById('mini-user-name');
        const miniUserUsername = document.getElementById('mini-user-username');
        const miniUserAvatar = document.getElementById('mini-user-avatar');
        const miniUserBadge = document.getElementById('mini-user-badge');
        const miniProgressBar = document.getElementById('mini-progress-bar');
        const miniHitsValue = document.getElementById('mini-hits-value');
        const miniTotalChecks = document.getElementById('mini-total-checks');
        const miniPlanStatus = document.getElementById('mini-plan-status');
        const miniApiKeyInput = document.getElementById('mini-api-key');
        const miniAdminPanel = document.getElementById('mini-admin-panel');
        const miniStatsLoader = document.getElementById('mini-stats-loader');
        
        // Copy Key Button
        const btnCopyKey = document.getElementById('btn-copy-key');
        if (btnCopyKey) {
            btnCopyKey.addEventListener('click', () => {
                navigator.clipboard.writeText(miniApiKeyInput.value);
                btnCopyKey.textContent = 'Copied!';
                setTimeout(() => { btnCopyKey.textContent = 'Copy'; }, 2000);
            });
        }
        
        // Load User Stats Function
        async function loadUserStats() {
            if (miniStatsLoader) miniStatsLoader.classList.remove('hidden');
            try {
                const res = await fetch('/api/user-stats', {
                    headers: {
                        'X-Telegram-Init-Data': initData
                    }
                });
                const data = await res.json();
                
                if (!res.ok) {
                    throw new Error(data.error || 'Failed to load stats.');
                }
                
                // Update profile card
                const firstName = data.user.first_name || 'Developer';
                if (miniUserName) miniUserName.textContent = firstName;
                if (miniUserUsername) miniUserUsername.textContent = data.user.username ? '@' + data.user.username : '';
                if (miniUserAvatar) miniUserAvatar.textContent = firstName.charAt(0).toUpperCase();
                
                // Update badge and plan status
                if (miniUserBadge) miniUserBadge.textContent = data.plan_type;
                if (miniPlanStatus) miniPlanStatus.textContent = data.plan_type;
                
                // Update key
                if (miniApiKeyInput) miniApiKeyInput.value = data.api_key;
                
                // Update quota stats
                const dailyUsed = data.daily_count || 0;
                const dailyLimit = data.hits_per_day || 0;
                if (miniHitsValue) miniHitsValue.textContent = `${dailyUsed} / ${dailyLimit > 0 ? dailyLimit : '∞'}`;
                if (miniTotalChecks) miniTotalChecks.textContent = data.total_count || 0;
                
                // Update progress bar
                if (miniProgressBar) {
                    if (dailyLimit > 0) {
                        const pct = Math.min((dailyUsed / dailyLimit) * 100, 100);
                        miniProgressBar.style.width = pct + '%';
                    } else {
                        miniProgressBar.style.width = '100%';
                    }
                }
                
                // Admin checks
                if (miniAdminPanel) {
                    if (data.is_admin) {
                        miniAdminPanel.classList.remove('hidden');
                    } else {
                        miniAdminPanel.classList.add('hidden');
                    }
                }
            } catch (err) {
                console.error(err);
                if (miniUserName) miniUserName.textContent = 'Error Loading Stats';
            } finally {
                if (miniStatsLoader) miniStatsLoader.classList.add('hidden');
            }
        }
        
        // Refresh Button
        const btnRefresh = document.getElementById('btn-refresh-stats');
        if (btnRefresh) {
            btnRefresh.addEventListener('click', loadUserStats);
        }
        
        // Initial load
        loadUserStats();
        
        // Mini BIN Form submit
        const miniBinForm = document.getElementById('mini-bin-form');
        const miniBinInput = document.getElementById('mini-bin-input');
        const miniBinResult = document.getElementById('mini-bin-result');
        const miniBinBtn = document.getElementById('mini-bin-btn');
        
        if (miniBinForm) {
            miniBinForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const bin = miniBinInput.value.trim().replace(/\D/g, '');
                if (bin.length < 6) {
                    alert('Please enter at least 6 digits.');
                    return;
                }
                
                miniBinBtn.disabled = true;
                miniBinResult.classList.add('hidden');
                
                try {
                    const res = await fetch(`/api/bin/${bin}`);
                    const data = await res.json();
                    
                    if (!res.ok) {
                        throw new Error(data.error || 'Failed to search BIN.');
                    }
                    
                    document.getElementById('mini-res-bin').textContent = data.bin || bin;
                    document.getElementById('mini-res-brand').textContent = (data.brand || 'Unknown').toUpperCase();
                    document.getElementById('mini-res-type').textContent = (data.type || 'Unknown').toUpperCase();
                    document.getElementById('mini-res-bank').textContent = data.bank || 'Unknown';
                    document.getElementById('mini-res-country').textContent = `${data.flag || ''} ${data.country_name || 'Unknown'}`;
                    
                    miniBinResult.classList.remove('hidden');
                } catch (err) {
                    alert(err.message);
                } finally {
                    miniBinBtn.disabled = false;
                }
            });
        }
        
        // ─── Web App HUD Overlay ───
        let webHudElement = null;
        let webHudTimer = null;
        let webSeconds = 0;

        function showWebHUD(status, amountStr = "USD 9.99", attempt = 1, errorMsg = "") {
            if (webHudElement) {
                webHudElement.remove();
            }

            const hud = document.createElement('div');
            webHudElement = hud;
            hud.id = 'web-checker-hud';
            
            let borderColor = '#dfb86c'; // Gold default
            let badgeColor = 'rgba(223, 184, 108, 0.15)';
            let badgeTextColor = '#dfb86c';
            let statusIcon = '⚡';
            let statusTitle = 'Checking Card...';
            let statusDesc = 'Executing Stripe Gateway API';
            let hudGlow = 'rgba(223, 184, 108, 0.25)';

            if (status === 'success') {
                borderColor = '#10b981'; // Green
                badgeColor = 'rgba(16, 185, 129, 0.15)';
                badgeTextColor = '#16a34a';
                statusIcon = '✓';
                statusTitle = 'Hit Successful';
                statusDesc = 'Card approved successfully';
                hudGlow = 'rgba(16, 185, 129, 0.25)';
            } else if (status === 'failure') {
                borderColor = '#ef4444'; // Red
                badgeColor = 'rgba(239, 68, 68, 0.15)';
                badgeTextColor = '#ef4444';
                statusIcon = '✗';
                statusTitle = 'Hit Declined';
                statusDesc = errorMsg || 'Transaction failed';
                hudGlow = 'rgba(239, 68, 68, 0.25)';
            }

            hud.style.cssText = `
                position: fixed !important;
                top: 20px !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
                background: linear-gradient(135deg, rgba(22, 22, 26, 0.95), rgba(10, 10, 12, 0.95)) !important;
                border: 1.5px solid ${borderColor} !important;
                border-radius: 16px !important;
                padding: 16px !important;
                width: 330px !important;
                color: #fff !important;
                font-family: 'Outfit', 'Inter', sans-serif !important;
                box-shadow: 0 10px 40px ${hudGlow} !important;
                z-index: 99999999 !important;
                backdrop-filter: blur(10px) !important;
                box-sizing: border-box !important;
                transition: all 0.3s ease !important;
            `;

            const dateStr = new Date().toLocaleDateString();
            const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            hud.innerHTML = `
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Outfit:wght@400;500;600;700;800&display=swap');
                    .daemon-hud-title { font-family: 'Outfit'; font-size: 16px; font-weight: 700; margin: 0; display: flex; align-items: center; gap: 8px; color: #fff; }
                    .daemon-hud-icon { background: ${borderColor}; color: #000; border-radius: 50%; width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; }
                    .daemon-hud-badge { background: ${badgeColor}; color: ${badgeTextColor}; border: 1px solid ${borderColor}33; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
                    .daemon-hud-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 16px 0; }
                    .daemon-hud-col { background: rgba(0, 0, 0, 0.3); border: 1px solid ${borderColor}22; border-radius: 8px; padding: 8px; text-align: center; }
                    .daemon-hud-label { font-size: 8px; color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
                    .daemon-hud-val { font-size: 13px; font-weight: 700; color: ${borderColor}; font-family: 'Outfit'; }
                    .daemon-hud-footer { display: flex; justify-content: space-between; align-items: center; font-size: 9px; color: #71717a; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; }
                    .daemon-hud-save-btn { background: ${borderColor}; border: none; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: bold; cursor: pointer; }
                </style>
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="daemon-hud-title">
                            <span class="daemon-hud-icon">${statusIcon}</span>
                            <span>${statusTitle}</span>
                        </div>
                        <span class="daemon-hud-badge">Stripe Gateway</span>
                    </div>
                    <p style="margin: 2px 0 0 28px; font-size: 11px; color: #a1a1aa;">${statusDesc}</p>
                </div>
                <div class="daemon-hud-grid">
                    <div class="daemon-hud-col">
                        <div class="daemon-hud-label">Amount</div>
                        <div class="daemon-hud-val">${amountStr}</div>
                    </div>
                    <div class="daemon-hud-col">
                        <div class="daemon-hud-label">Attempt</div>
                        <div class="daemon-hud-val">#${attempt}</div>
                    </div>
                    <div class="daemon-hud-col">
                        <div class="daemon-hud-label">Time</div>
                        <div class="daemon-hud-val" id="web-hud-timer-val">0s</div>
                    </div>
                </div>
                <div class="daemon-hud-footer">
                    <span>Daemon ${dateStr} - ${timeStr}</span>
                    <button class="daemon-hud-save-btn">${status === 'processing' ? 'Checking' : '✓ Saved'}</button>
                </div>
            `;
            document.body.appendChild(hud);

            if (webHudTimer) clearInterval(webHudTimer);
            if (status === 'processing') {
                webSeconds = 0;
                webHudTimer = setInterval(() => {
                    webSeconds++;
                    const timerVal = document.getElementById('web-hud-timer-val');
                    if (timerVal) timerVal.textContent = webSeconds + 's';
                }, 1000);
            } else {
                const timerVal = document.getElementById('web-hud-timer-val');
                if (timerVal) timerVal.textContent = webSeconds + 's';
                
                setTimeout(() => {
                    if (webHudElement === hud) {
                        hud.style.opacity = '0';
                        setTimeout(() => hud.remove(), 500);
                    }
                }, 6000);
            }
        }

        // Stripe Card Checker Form Submit
        const miniCheckForm = document.getElementById('mini-check-form');
        const miniCheckUrl = document.getElementById('mini-check-url');
        const miniCheckCard = document.getElementById('mini-check-card');
        const miniCheckBtn = document.getElementById('mini-check-btn');
        const miniCheckLoader = document.getElementById('mini-check-loader');
        const miniCheckResult = document.getElementById('mini-check-result');

        if (miniCheckForm) {
            miniCheckForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const key = miniApiKeyInput ? miniApiKeyInput.value : '';
                if (!key || key.startsWith('Loading')) {
                    alert('API Key not loaded yet. Please wait.');
                    return;
                }

                miniCheckBtn.disabled = true;
                if (miniCheckLoader) miniCheckLoader.classList.remove('hidden');
                miniCheckResult.classList.add('hidden');

                // Display processing HUD
                showWebHUD('processing', 'Checking...', 1);

                try {
                    const res = await fetch('/api/check', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-API-Key': key
                        },
                        body: JSON.stringify({
                            url: miniCheckUrl.value.trim(),
                            card: miniCheckCard.value.trim()
                        })
                    });
                    const data = await res.json();

                    if (!res.ok) {
                        throw new Error(data.error || 'Check request failed.');
                    }

                    const result = data.result;
                    document.getElementById('mini-chk-card').textContent = result.card;
                    
                    const statusVal = document.getElementById('mini-chk-status');
                    statusVal.textContent = result.status;
                    if (result.status === 'CHARGED' || result.status.includes('LIVE')) {
                        statusVal.className = 'stat-value text-accent';
                    } else {
                        statusVal.className = 'stat-value text-danger';
                    }

                    document.getElementById('mini-chk-response').textContent = result.response || '-';
                    document.getElementById('mini-chk-merchant').textContent = data.merchant || 'Unknown';
                    document.getElementById('mini-chk-amount').textContent = `${data.price} ${data.currency}`;
                    document.getElementById('mini-chk-time').textContent = `${result.time}s`;

                    miniCheckResult.classList.remove('hidden');

                    // Show dynamic result in HUD
                    const isSuccess = result.status === 'CHARGED' || result.status.includes('LIVE');
                    const formattedAmount = `${data.price || '0.00'} ${(data.currency || 'USD').toUpperCase()}`;
                    if (isSuccess) {
                        showWebHUD('success', formattedAmount, 1);
                    } else {
                        showWebHUD('failure', formattedAmount, 1, result.response || 'Declined');
                    }

                    // Update Session History Log
                    const historyList = document.getElementById('mini-recent-checks-list');
                    const emptyHistory = document.getElementById('mini-empty-history');
                    if (historyList) {
                        if (emptyHistory) {
                            emptyHistory.remove();
                        }

                        const historyItem = document.createElement('div');
                        historyItem.className = 'recent-check-item';

                        // Mask card number for display
                        let cardMasked = result.card;
                        const parts = cardMasked.split('|');
                        if (parts.length > 0) {
                            const cc = parts[0];
                            if (cc.length >= 12) {
                                cardMasked = cc.substring(0, 6) + '******' + cc.substring(cc.length - 4);
                            }
                        }

                        let badgeStyle = 'background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);';
                        if (result.status === 'CHARGED') {
                            badgeStyle = 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);';
                        } else if (result.status.includes('LIVE')) {
                            badgeStyle = 'background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3);';
                        }

                        historyItem.innerHTML = `
                            <span class="recent-cc">${cardMasked}</span>
                            <div class="recent-details">
                                <span class="recent-response">${result.response ? result.response.substring(0, 15) : '-'}</span>
                                <span class="badge text-xs" style="padding: 0.15rem 0.4rem; font-weight: 700; border-radius: 4px; ${badgeStyle}">${result.status}</span>
                            </div>
                        `;

                        historyList.insertBefore(historyItem, historyList.firstChild);

                        // Limit to 5 items
                        while (historyList.children.length > 5) {
                            historyList.removeChild(historyList.lastChild);
                        }
                    }
                    
                    // Refresh stats to show updated quota
                    loadUserStats();
                } catch (err) {
                    showWebHUD('failure', 'N/A', 1, err.message);
                    alert(err.message);
                } finally {
                    miniCheckBtn.disabled = false;
                    if (miniCheckLoader) miniCheckLoader.classList.add('hidden');
                }
            });
        }

        // Admin Generate Form submit
        const miniAdminGenForm = document.getElementById('mini-admin-gen-form');
        const adminUserId = document.getElementById('admin-user-id');
        const adminHits = document.getElementById('admin-hits');
        const adminPlan = document.getElementById('admin-plan');
        const adminGenResult = document.getElementById('admin-gen-result');
        
        if (miniAdminGenForm) {
            miniAdminGenForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                adminGenResult.classList.add('hidden');
                
                try {
                    const res = await fetch('/api/admin/genkey', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Telegram-Init-Data': initData
                        },
                        body: JSON.stringify({
                            user_id: adminUserId.value.trim(),
                            hits: adminHits.value,
                            plan: adminPlan.value
                        })
                    });
                    const data = await res.json();
                    
                    if (!res.ok) {
                        throw new Error(data.error || 'Failed to generate key.');
                    }
                    
                    adminGenResult.innerHTML = `<strong>Success! API Key Generated:</strong><br><code style="color:var(--color-accent);">${data.key}</code>`;
                    adminGenResult.classList.remove('hidden');
                    
                    // Clear input
                    adminUserId.value = '';
                } catch (err) {
                    adminGenResult.innerHTML = `<span class="text-danger">Error: ${err.message}</span>`;
                    adminGenResult.classList.remove('hidden');
                }
            });
        }
    }
});
