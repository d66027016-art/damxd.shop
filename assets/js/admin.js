// Render Dashboard statistics
function renderVendorDashboard() {
    const s1 = document.getElementById('salesCounter');
    if (!s1) return;
    s1.textContent = `$${salesStats.totalRevenue.toLocaleString()}`;
    document.getElementById('soldCounter').textContent = salesStats.countSold;
    document.getElementById('listingsCounter').textContent = products.length;

    const avg = products.length > 0 ? (products.reduce((s, p) => s + p.price, 0) / products.length) : 0;
    document.getElementById('avgPriceCounter').textContent = `$${avg.toFixed(2)}`;

    const tbody = document.getElementById('inventoryTableBody');
    tbody.innerHTML = '';

    products.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight:600; color:#fff;">${p.name}</td>
            <td style="font-family:var(--font-mono);">${p.bin}</td>
            <td style="font-family:var(--font-mono); color:var(--primary);">$${p.price}</td>
            <td><span style="color:#10b981; font-weight:700;">${p.health}%</span></td>
            <td>
                <button class="btn" style="padding:6px 12px; font-size:10px; display:inline-block;" onclick="deleteListing(${p.id})">
                    <i class="fa-solid fa-trash" style="color:var(--accent);"></i> Delete
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    renderWalletBalances();
    updateConnectionUI();
}

function renderWalletBalances() {
    const tbody = document.getElementById('adminWalletBalancesBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    const allUsers = JSON.parse(localStorage.getItem('nexus_users')) || [];
    
    if (allUsers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--text-muted);">No registered users yet.</td></tr>';
        return;
    }

    allUsers.forEach(u => {
        const userBalance = parseFloat(localStorage.getItem(`nexus_balance_${u.username}`)) || 0.00;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight:600; color:#fff;">${u.username}</td>
            <td style="text-transform:capitalize;">${u.role}</td>
            <td style="font-family:var(--font-mono); color:var(--success); font-weight:700;">$${userBalance.toFixed(2)}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ------------------ CONNECTION GATEWAY SYSTEM ------------------
function updateConnectionUI() {
    const badgeEl = document.getElementById('headerConnectionStatus');
    if (badgeEl) {
        badgeEl.innerHTML = `<span style="display:inline-block; width:8px; height:8px; background:#00ff66; border-radius:50%; margin-right:6px; box-shadow: 0 0 8px #00ff66;"></span>${connectionState.activeNode} (${connectionState.latency}ms)`;
    }

    const modalNode = document.getElementById('connActiveNode');
    if (modalNode) {
        modalNode.textContent = connectionState.activeNode;
        document.getElementById('connLatency').textContent = `${connectionState.latency} ms`;
        document.getElementById('connProtocol').textContent = connectionState.protocol;
        document.getElementById('connPeers').textContent = `${connectionState.peers} active peers`;
        
        document.querySelectorAll('.conn-option-btn').forEach(btn => {
            if (btn.getAttribute('data-node') === connectionState.activeNode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
}

// Latency fluctuation
setInterval(() => {
    const activeNodeData = connectionState.nodesList.find(n => n.name === connectionState.activeNode);
    if (activeNodeData) {
        const delta = Math.floor(Math.random() * 7) - 3;
        let newLatency = connectionState.latency + delta;
        if (newLatency < activeNodeData.minLatency) newLatency = activeNodeData.minLatency;
        if (newLatency > activeNodeData.maxLatency) newLatency = activeNodeData.maxLatency;
        connectionState.latency = newLatency;
        
        const peersDelta = Math.floor(Math.random() * 3) - 1;
        let newPeers = connectionState.peers + peersDelta;
        if (newPeers < activeNodeData.basePeers - 2) newPeers = activeNodeData.basePeers - 2;
        if (newPeers > activeNodeData.basePeers + 4) newPeers = activeNodeData.basePeers + 4;
        connectionState.peers = newPeers;
        
        persistState();
        updateConnectionUI();
    }
}, 3000);

function switchGatewayNode(nodeName) {
    const nodeData = connectionState.nodesList.find(n => n.name === nodeName);
    if (nodeData) {
        connectionState.activeNode = nodeData.name;
        connectionState.protocol = nodeData.protocol;
        connectionState.latency = Math.floor((nodeData.minLatency + nodeData.maxLatency) / 2);
        connectionState.peers = nodeData.basePeers;
        
        persistState();
        updateConnectionUI();
        logMessage(`Switched gateway endpoint path: [${nodeData.name}] via protocol ${nodeData.protocol}`, "SYSTEM");
        showToast(`Connected to gateway: ${nodeData.name}`);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Initial render of inventory
    renderVendorDashboard();

    updateConnectionUI();

    const openConnBtn = document.getElementById('headerConnectionStatus');
    if (openConnBtn) {
        openConnBtn.addEventListener('click', () => {
            document.getElementById('connectionModal').classList.add('active');
            logMessage('Network connection gateways modal opened.');
        });
    }

    const closeConnBtn = document.getElementById('closeConnectionBtn');
    if (closeConnBtn) {
        closeConnBtn.addEventListener('click', () => {
            document.getElementById('connectionModal').classList.remove('active');
        });
    }

    document.querySelectorAll('.conn-option-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const selectedNode = this.getAttribute('data-node');
            switchGatewayNode(selectedNode);
        });
    });

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('nexus_session');
            window.location.href = '/login';
        });
    }
});

function deleteListing(id) {
    const index = products.findIndex(p => p.id === id);
    if (index > -1) {
        const deletedName = products[index].name;
        products.splice(index, 1);
        persistState();
        renderVendorDashboard();
        showToast(`Deleted listing: ${deletedName}`, "error");
        logMessage(`Listing deleted by vendor: ${deletedName}`, "WARNING");
    }
}

// Tab selection swaps
if (document.getElementById('tabInventoryBtn')) {
    document.getElementById('tabInventoryBtn').addEventListener('click', function() {
        document.querySelectorAll('.dashboard-panel .tab-btn').forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');
        document.getElementById('inventoryPanel').style.display = 'block';
        document.getElementById('addListingPanel').style.display = 'none';
        document.getElementById('walletManagerPanel').style.display = 'none';
        document.getElementById('usersPanel').style.display = 'none';
    });

    document.getElementById('tabAddListingBtn').addEventListener('click', function() {
        document.querySelectorAll('.dashboard-panel .tab-btn').forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');
        document.getElementById('inventoryPanel').style.display = 'none';
        document.getElementById('addListingPanel').style.display = 'block';
        document.getElementById('walletManagerPanel').style.display = 'none';
        document.getElementById('usersPanel').style.display = 'none';
    });

    document.getElementById('tabWalletManagerBtn').addEventListener('click', function() {
        document.querySelectorAll('.dashboard-panel .tab-btn').forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');
        document.getElementById('inventoryPanel').style.display = 'none';
        document.getElementById('addListingPanel').style.display = 'none';
        document.getElementById('walletManagerPanel').style.display = 'block';
        document.getElementById('usersPanel').style.display = 'none';
        renderWalletBalances();
    });

    const tabUsersBtn = document.getElementById('tabUsersBtn');
    if (tabUsersBtn) {
        tabUsersBtn.addEventListener('click', function() {
            document.querySelectorAll('.dashboard-panel .tab-btn').forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            document.getElementById('inventoryPanel').style.display = 'none';
            document.getElementById('addListingPanel').style.display = 'none';
            document.getElementById('walletManagerPanel').style.display = 'none';
            document.getElementById('usersPanel').style.display = 'block';
            renderUsersPanel();
        });
    }
}

// ------------------ USER MANAGEMENT PANEL ------------------
function renderUsersPanel() {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const allUsers = JSON.parse(localStorage.getItem('nexus_users')) || [];

    if (allUsers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:30px;"><i class="fa-solid fa-users-slash" style="font-size:24px; display:block; margin-bottom:10px;"></i>No registered users yet.</td></tr>';
        return;
    }

    allUsers.forEach((u, index) => {
        const userBalance = parseFloat(localStorage.getItem(`nexus_balance_${u.username}`)) || 0.00;
        const recoveryCodes = u.recoveryCodes ? u.recoveryCodes.length : 0;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight:600; color:#fff;">${u.username}</td>
            <td style="text-transform:capitalize; color:var(--text-muted);">${u.role}</td>
            <td style="font-family:var(--font-mono); color:var(--success);">$${userBalance.toFixed(2)}</td>
            <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted);">${recoveryCodes} codes left</td>
            <td style="display:flex; gap:8px;">
                <button class="btn" style="padding:6px 12px; font-size:10px;" onclick="resetUserBalance(${index})">
                    <i class="fa-solid fa-wallet" style="color:var(--warning);"></i> Reset Balance
                </button>
                <button class="btn" style="padding:6px 12px; font-size:10px;" onclick="deleteUser(${index})">
                    <i class="fa-solid fa-user-slash" style="color:var(--error);"></i> Delete
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function deleteUser(index) {
    const allUsers = JSON.parse(localStorage.getItem('nexus_users')) || [];
    if (index < 0 || index >= allUsers.length) return;
    const deletedName = allUsers[index].username;
    allUsers.splice(index, 1);
    localStorage.setItem('nexus_users', JSON.stringify(allUsers));
    renderUsersPanel();
    showToast(`User "${deletedName}" deleted.`, 'error');
    logMessage(`Admin deleted user account: ${deletedName}`, 'WARNING');
}

function resetUserBalance(index) {
    const allUsers = JSON.parse(localStorage.getItem('nexus_users')) || [];
    if (index < 0 || index >= allUsers.length) return;
    const u = allUsers[index];
    localStorage.setItem(`nexus_balance_${u.username}`, '0');
    renderUsersPanel();
    showToast(`Wallet balance reset for "${u.username}".`);
    logMessage(`Admin reset wallet balance for user: ${u.username}`, 'WARNING');
}

// Listing creator submission
if (document.getElementById('newListingForm')) {
    document.getElementById('newListingForm').addEventListener('submit', function(e) {
        e.preventDefault();

        const newCard = {
            id: Date.now(),
            name: document.getElementById('prodName').value.trim(),
            price: parseFloat(document.getElementById('prodPrice').value),
            brand: document.getElementById('prodBrand').value,
            tier: document.getElementById('prodTier').value,
            bin: document.getElementById('prodBin').value.trim(),
            country: document.getElementById('prodCountry').value.toUpperCase().trim(),
            limit: parseInt(document.getElementById('prodLimit').value),
            health: parseInt(document.getElementById('prodHealth').value),
            desc: document.getElementById('prodDesc').value.trim(),
            billingName: document.getElementById('prodBillName').value.trim(),
            billingAddress: document.getElementById('prodBillAddress').value.trim(),
            billingCityStateZip: document.getElementById('prodBillCityStateZip').value.trim(),
            billingPhone: document.getElementById('prodBillPhone').value.trim()
        };

        products.unshift(newCard);
        persistState();
        renderVendorDashboard();
        
        document.getElementById('tabInventoryBtn').click();
        showToast(`Listed "${newCard.name}" successfully!`);
        logMessage(`New card listing published: ${newCard.name} (BIN ${newCard.bin})`);
        
        this.reset();
    });
}

// Credit Wallet Submission
if (document.getElementById('adminCreditWalletForm')) {
    document.getElementById('adminCreditWalletForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const targetUsername = document.getElementById('creditUsername').value.trim();
        const amt = parseFloat(document.getElementById('creditAmount').value);
        if (isNaN(amt) || amt <= 0) return;
        
        const key = targetUsername ? `nexus_balance_${targetUsername}` : 'nexus_balance';
        let currentBal = parseFloat(localStorage.getItem(key)) || 0.00;
        currentBal += amt;
        localStorage.setItem(key, currentBal);
        
        showToast(`Successfully credited $${amt.toFixed(2)} to ${targetUsername || 'buyer'}!`);
        logMessage(`Vendor credited $${amt.toFixed(2)} to user account [${targetUsername || 'buyer'}].`, 'SYSTEM');
        
        renderWalletBalances();
        this.reset();
    });
}
