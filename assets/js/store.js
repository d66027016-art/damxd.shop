// Helper to match card theme color gradients
function getCardGradient(brand) {
    switch (brand) {
        case 'Visa': return 'var(--card-visa)';
        case 'Mastercard': return 'var(--card-mastercard)';
        case 'Amex': return 'var(--card-amex)';
        case 'Discover': return 'var(--card-discover)';
        default: return 'var(--card-default)';
    }
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
        
        // Highlight active radio/button
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
        const delta = Math.floor(Math.random() * 7) - 3; // -3 to +3
        let newLatency = connectionState.latency + delta;
        if (newLatency < activeNodeData.minLatency) newLatency = activeNodeData.minLatency;
        if (newLatency > activeNodeData.maxLatency) newLatency = activeNodeData.maxLatency;
        connectionState.latency = newLatency;
        
        const peersDelta = Math.floor(Math.random() * 3) - 1; // -1 to +1
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

// Bind connection clicks
document.addEventListener('DOMContentLoaded', () => {
    updateConnectionUI();

    const openConnBtn = document.getElementById('headerConnectionStatus');
    if (openConnBtn) {
        openConnBtn.addEventListener('click', () => {
            document.getElementById('connectionModal').classList.add('active');
            logMessage("Network connection gateways modal opened.");
        });
    }

    const closeConnBtn = document.getElementById('closeConnectionBtn');
    if (closeConnBtn) {
        closeConnBtn.addEventListener('click', () => {
            closeModal('connectionModal');
        });
    }

    document.querySelectorAll('.conn-option-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const selectedNode = this.getAttribute('data-node');
            switchGatewayNode(selectedNode);
        });
    });
});

// Helper to match Brand icon logos
function getBrandIcon(brand) {
    switch (brand) {
        case 'Visa': return '<i class="fa-brands fa-cc-visa"></i>';
        case 'Mastercard': return '<i class="fa-brands fa-cc-mastercard"></i>';
        case 'Amex': return '<i class="fa-brands fa-cc-amex"></i>';
        case 'Discover': return '<i class="fa-brands fa-cc-discover"></i>';
        default: return '<i class="fa-solid fa-credit-card"></i>';
    }
}

const sessionDetails = JSON.parse(localStorage.getItem('nexus_session'));
if (sessionDetails && document.getElementById('shopUsername')) {
    document.getElementById('shopUsername').textContent = sessionDetails.username;
}

// ------------------ RENDERING STOREFRONT ------------------
function renderStore() {
    const listEl = document.getElementById('productList');
    if (!listEl) return;
    listEl.innerHTML = '';

    const searchVal = document.getElementById('searchInput').value.toLowerCase().trim();
    const brandVal = document.getElementById('brandFilter').value;
    const tierVal = document.getElementById('tierFilter').value;
    const sortVal = document.getElementById('sortControl').value;

    products = JSON.parse(localStorage.getItem('nexus_products')) || initialProducts;

    let filtered = products.filter(p => {
        const matchesSearch = p.name.toLowerCase().includes(searchVal) || 
                              p.desc.toLowerCase().includes(searchVal) || 
                              p.bin.includes(searchVal) || 
                              p.country.toLowerCase().includes(searchVal);
        const matchesBrand = brandVal === 'all' || p.brand === brandVal;
        const matchesTier = tierVal === 'all' || p.tier === tierVal;
        return matchesSearch && matchesBrand && matchesTier;
    });

    if (sortVal === 'price-asc') {
        filtered.sort((a, b) => a.price - b.price);
    } else if (sortVal === 'price-desc') {
        filtered.sort((a, b) => b.price - a.price);
    } else if (sortVal === 'health') {
        filtered.sort((a, b) => b.health - a.health);
    }

    if (filtered.length === 0) {
        listEl.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 50px; color: var(--text-muted);">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 32px; margin-bottom: 15px; color: var(--accent);"></i>
                <h3>No cards match your search parameters.</h3>
            </div>
        `;
        return;
    }

    filtered.forEach(p => {
        const article = document.createElement('article');
        article.className = 'product-card';
        article.innerHTML = `
            <div>
                <div class="card-visual-wrapper">
                    <div class="card-visual-inner">
                        <div class="card-visual-front" style="background: ${getCardGradient(p.brand)}">
                            <div class="card-chip"></div>
                            <div class="card-brand">${getBrandIcon(p.brand)} ${p.brand}</div>
                            <div class="card-number">${p.bin}•••• •••• ••••</div>
                            <div class="card-meta">
                                <div>
                                    <div style="font-size:7px; opacity:0.6; margin-bottom: 2px;">Holder</div>
                                    <div>CARDMEMBER</div>
                                </div>
                                <div>
                                    <div style="font-size:7px; opacity:0.6; margin-bottom: 2px;">Region</div>
                                    <div style="font-size:11px; font-weight:700;"><i class="fa-solid fa-earth-americas"></i> ${p.country}</div>
                                </div>
                            </div>
                        </div>
                        <div class="card-visual-back" style="background: ${getCardGradient(p.brand)}">
                            <div class="card-magstripe"></div>
                            <div class="card-sig-cvv-row">
                                <div class="card-signature"></div>
                                <div class="card-cvv">•••</div>
                            </div>
                            <div class="card-hologram"></div>
                        </div>
                    </div>
                </div>

                <div class="card-info">
                    <div class="card-title-line">
                        <h3>${p.name}</h3>
                        <div class="price-text">$${p.price}</div>
                    </div>
                    <p class="desc-text">${p.desc}</p>
                </div>
            </div>

            <div>
                <div class="badges-line">
                    <span class="badge-info"><i class="fa-solid fa-fingerprint"></i> BIN: ${p.bin}</span>
                    <span class="badge-info"><i class="fa-solid fa-location-dot"></i> Billing: YES</span>
                    <span class="badge-info high-success"><i class="fa-solid fa-bolt"></i> Health: ${p.health}%</span>
                </div>

                <div style="display: flex; gap: 10px;">
                    <button class="btn" style="flex: 1;" onclick="openDetailsModal(${p.id})">Details</button>
                    <button class="btn btn-primary" style="flex: 1;" onclick="addToCart(${p.id})">
                        <i class="fa-solid fa-cart-plus"></i> Add
                    </button>
                </div>
            </div>
        `;
        listEl.appendChild(article);
    });
}

// ------------------ CART DRAW PANEL FUNCTIONS ------------------
function updateCartUI() {
    const countEl = document.getElementById('cartCount');
    const itemsListEl = document.getElementById('cartItemsList');
    const totalTextEl = document.getElementById('cartTotalText');
    if (!countEl) return;

    countEl.textContent = cart.length;
    itemsListEl.innerHTML = '';

    if (cart.length === 0) {
        itemsListEl.innerHTML = `
            <div style="text-align: center; color: var(--text-dim); margin-top: 60px;">
                <i class="fa-solid fa-basket-shopping" style="font-size: 40px; margin-bottom:15px;"></i>
                <p>Shopping cart is currently empty.</p>
            </div>
        `;
        totalTextEl.textContent = "$0.00";
        return;
    }

    let total = 0;
    cart.forEach((item, idx) => {
        total += item.price;
        const row = document.createElement('div');
        row.className = 'cart-item-row';
        row.innerHTML = `
            <div class="cart-item-details">
                <h4>${item.name}</h4>
                <span>$${item.price}</span>
            </div>
            <button class="remove-btn" onclick="removeFromCart(${idx})"><i class="fa-solid fa-trash-can"></i></button>
        `;
        itemsListEl.appendChild(row);
    });

    totalTextEl.textContent = `$${total.toFixed(2)}`;
}

function addToCart(id) {
    const prod = products.find(p => p.id === id);
    if (prod) {
        cart.push(prod);
        persistState();
        updateCartUI();
        logMessage(`Listing added to cart: ${prod.name} (BIN ${prod.bin})`);
        showToast(`Successfully added ${prod.name} to cart.`);
    }
}

function removeFromCart(idx) {
    const item = cart[idx];
    if (item) {
        cart.splice(idx, 1);
        persistState();
        updateCartUI();
        logMessage(`Listing removed from cart: ${item.name}`, "WARNING");
        showToast(`Removed ${item.name} from cart.`, 'error');
    }
}

// ------------------ PRODUCT DETAILS MODAL ------------------
function openDetailsModal(id) {
    const p = products.find(prod => prod.id === id);
    if (!p) return;

    const bodyEl = document.getElementById('detailModalBody');
    bodyEl.innerHTML = `
        <div class="card-visual-wrapper" style="height: 190px; margin-bottom: 30px;">
            <div class="card-visual-inner">
                <div class="card-visual-front" style="background: ${getCardGradient(p.brand)}; padding: 22px;">
                    <div class="card-chip" style="width: 44px; height: 32px;"></div>
                    <div class="card-brand" style="font-size: 22px;">${getBrandIcon(p.brand)} ${p.brand}</div>
                    <div class="card-number" style="font-size: 19px; margin: 20px 0;">${p.bin}•••• •••• ••••</div>
                    <div class="card-meta">
                        <div>
                            <div style="font-size:8px; opacity:0.6; margin-bottom: 2px;">Holder</div>
                            <div>CARDMEMBER</div>
                        </div>
                        <div>
                            <div style="font-size:8px; opacity:0.6; margin-bottom: 2px;">ISO Region</div>
                            <div style="font-size:12px; font-weight:700;"><i class="fa-solid fa-earth-europe"></i> ${p.country}</div>
                        </div>
                    </div>
                </div>
                <div class="card-visual-back" style="background: ${getCardGradient(p.brand)}">
                    <div class="card-magstripe"></div>
                    <div class="card-sig-cvv-row">
                        <div class="card-signature"></div>
                        <div class="card-cvv">777</div>
                    </div>
                    <div class="card-hologram"></div>
                </div>
            </div>
        </div>

        <h2 style="font-family: var(--font-display); color: #fff; margin-bottom: 8px;">${p.name}</h2>
        <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 25px;">${p.desc}</p>

        <div class="details-grid-wrapper">
            <div class="detail-card-panel">
                <label><i class="fa-solid fa-fingerprint"></i> BIN Identification</label>
                <span>${p.bin}</span>
            </div>
            <div class="detail-card-panel">
                <label><i class="fa-solid fa-gem"></i> Level Class</label>
                <span>${p.tier}</span>
            </div>
            <div class="detail-card-panel">
                <label><i class="fa-solid fa-vault"></i> Balance Limit</label>
                <span style="font-family: var(--font-mono);">$${p.limit.toLocaleString()}</span>
            </div>
            <div class="detail-card-panel">
                <label><i class="fa-solid fa-tags"></i> Price</label>
                <span style="color: var(--primary); font-family: var(--font-mono);">$${p.price}</span>
            </div>
        </div>

        <div class="detail-card-panel" style="grid-column: span 2; margin-bottom: 20px;">
            <label><i class="fa-solid fa-location-dot"></i> Billing Information Included</label>
            <span style="color:#00ff66; font-size:13px;"><i class="fa-solid fa-shield-halved"></i> Billing Name, Street Address, Zip Code, and Phone details are secured & provided post-checkout.</span>
        </div>

        <div class="rating-bar-wrapper">
            <div class="rating-labels">
                <span style="color:var(--text-muted); text-transform:uppercase; font-size:11px; letter-spacing:0.5px;">Estimated Success Health</span>
                <span style="color: #10b981; font-weight: 700; font-family: var(--font-mono);">${p.health}%</span>
            </div>
            <div class="rating-bar-bg">
                <div class="rating-bar-fill" id="modalRatingBar"></div>
            </div>
        </div>

        <div style="display: flex; gap: 15px; margin-top: 35px;">
            <button class="btn" style="flex: 1;" onclick="closeModal('detailModal')">Go Back</button>
            <button class="btn btn-primary" style="flex: 1;" onclick="addToCart(${p.id}); closeModal('detailModal');">
                <i class="fa-solid fa-cart-plus"></i> Add To Cart
            </button>
        </div>
    `;

    document.getElementById('detailModal').classList.add('active');
    logMessage(`Detailed modal view opened for: ${p.name}`);
    
    setTimeout(() => {
        const fill = document.getElementById('modalRatingBar');
        if (fill) fill.style.width = p.health + '%';
    }, 50);
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
}

// ------------------ INTERACTIVE TOOLS CONTROLLER ------------------
if (document.getElementById('openToolsBtn')) {
    document.getElementById('openToolsBtn').addEventListener('click', () => {
        document.getElementById('toolsModal').classList.add('active');
        logMessage("Checker Utilities modal opened.");
    });
}

if (document.getElementById('closeToolsBtn')) {
    document.getElementById('closeToolsBtn').addEventListener('click', () => {
        closeModal('toolsModal');
    });
}

// Tools tab switches
const tabBinBtn = document.getElementById('tabBinToolBtn');
if (tabBinBtn) {
    tabBinBtn.addEventListener('click', function() {
        switchToolsTab(this, 'binToolPanel');
    });
}
const tabGenBtn = document.getElementById('tabGenToolBtn');
if (tabGenBtn) {
    tabGenBtn.addEventListener('click', function() {
        switchToolsTab(this, 'genToolPanel');
    });
}
const tabCheckBtn = document.getElementById('tabCheckToolBtn');
if (tabCheckBtn) {
    tabCheckBtn.addEventListener('click', function() {
        switchToolsTab(this, 'checkToolPanel');
    });
}

function switchToolsTab(tabEl, panelId) {
    document.querySelectorAll('#toolsModal .tab-btn').forEach(btn => btn.classList.remove('active'));
    tabEl.classList.add('active');
    
    document.getElementById('binToolPanel').style.display = 'none';
    document.getElementById('genToolPanel').style.display = 'none';
    document.getElementById('checkToolPanel').style.display = 'none';
    
    document.getElementById(panelId).style.display = 'block';
}

// BIN LOOKUP ENGINE
if (document.getElementById('runBinCheckerBtn')) {
    document.getElementById('runBinCheckerBtn').addEventListener('click', () => {
        const binInput = document.getElementById('checkerBin').value.trim();
        const resultBox = document.getElementById('binCheckerResult');
        
        if (binInput.length < 6) {
            showToast("Please enter a valid 6-digit BIN number", "error");
            return;
        }

        // Real BIN details mapping
        let inferredBrand = "Visa";
        let cardLevel = "Classic Standard";
        let accountType = "DEBIT";
        let issuingBank = "JPMorgan Chase Bank, N.A.";
        let countryName = "UNITED STATES (US)";

        if (binInput === "406032") {
            inferredBrand = "Visa";
            cardLevel = "Classic Standard";
            accountType = "DEBIT";
            issuingBank = "JPMorgan Chase Bank, N.A.";
            countryName = "UNITED STATES (US)";
        } else if (binInput === "541275") {
            inferredBrand = "Mastercard";
            cardLevel = "Gold Premium";
            accountType = "CREDIT";
            issuingBank = "Deutsche Bank AG";
            countryName = "GERMANY (DE)";
        } else if (binInput === "378282") {
            inferredBrand = "Amex";
            cardLevel = "Platinum Premium";
            accountType = "CREDIT";
            issuingBank = "American Express Company";
            countryName = "UNITED STATES (US)";
        } else {
            const mockBanks = ["Chase Bank", "Bank of America", "Wells Fargo", "Barclays Bank", "HSBC Holdings", "BNP Paribas"];
            const mockLevels = ["Classic Standard", "Gold Premium", "Platinum Elite", "Infinite Black"];
            
            inferredBrand = binInput.startsWith('4') ? 'Visa' : binInput.startsWith('5') ? 'Mastercard' : binInput.startsWith('3') ? 'Amex' : 'Discover';
            cardLevel = mockLevels[Math.floor(Math.random() * mockLevels.length)];
            accountType = Math.random() > 0.5 ? "CREDIT" : "DEBIT";
            issuingBank = mockBanks[Math.floor(Math.random() * mockBanks.length)];
            countryName = binInput.startsWith('4') || binInput.startsWith('3') ? "UNITED STATES (US)" : "EUROPE (EU)";
        }

        resultBox.style.display = 'block';
        resultBox.innerHTML = `
            <div style="color:var(--primary); font-weight:bold; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:5px;">
                <i class="fa-solid fa-circle-nodes"></i> BIN DIRECTORY LOOKUP SUCCESSFUL
            </div>
            <strong>BIN Prefix:</strong> ${binInput}<br>
            <strong>Network Brand:</strong> ${inferredBrand}<br>
            <strong>Card Class:</strong> ${cardLevel}<br>
            <strong>Account Type:</strong> ${accountType}<br>
            <strong>Issuing Bank:</strong> ${issuingBank}<br>
            <strong>Country Region:</strong> ${countryName}<br>
            <strong>Registry Status:</strong> ACTIVE / HEALTHY (100%)
        `;
        logMessage(`BIN checker tool invoked for BIN: ${binInput}`);
    });
}

let lastGeneratedCards = [];

// TEST CC GENERATOR ENGINE
if (document.getElementById('runCcGeneratorBtn')) {
    document.getElementById('runCcGeneratorBtn').addEventListener('click', () => {
        const resultBox = document.getElementById('genCardResult');
        let customBin = document.getElementById('genBinPrefix').value.trim().replace(/\D/g, '');
        let amount = parseInt(document.getElementById('genAmount').value) || 10;
        if (amount < 1) amount = 1;
        if (amount > 100) amount = 100;

        let binPrefix = customBin;
        if (!binPrefix) {
            binPrefix = '411122';
        }

        const isAmex = binPrefix.startsWith('34') || binPrefix.startsWith('37');
        const cardLength = isAmex ? 15 : 16;
        const requiredRandomDigits = cardLength - binPrefix.length - 1; // leave 1 space for Luhn check digit

        let generatedCardsHTML = '';
        lastGeneratedCards = [];

        for (let i = 0; i < amount; i++) {
            let partialNum = binPrefix;
            for (let j = 0; j < requiredRandomDigits; j++) {
                partialNum += Math.floor(Math.random() * 10);
            }
            
            // Luhn completion check digit
            let checkDigit = 0;
            for (let d = 0; d <= 9; d++) {
                if (jsLuhnCheck(partialNum + d)) {
                    checkDigit = d;
                    break;
                }
            }
            
            const cardNum = partialNum + checkDigit;
            const expMonth = String(Math.floor(Math.random() * 12) + 1).padStart(2, '0');
            const expYear = Math.floor(Math.random() * 5) + 29;
            const cvv = isAmex ? Math.floor(1000 + Math.random() * 8999) : Math.floor(100 + Math.random() * 899);

            const cardStr = `${cardNum}|${expMonth}/${expYear}|${cvv}`;
            lastGeneratedCards.push(cardStr);

            generatedCardsHTML += `
                <div style="border-bottom: 1px solid rgba(255,255,255,0.05); padding: 8px 0;">
                    <input class="form-control-input" style="font-family:var(--font-mono); font-size:11px; margin:3px 0; color:var(--primary); width:100%;" value="${cardStr}" readonly />
                </div>
            `;
        }

        const mockNames = ["John Doe", "Jane Smith", "Robert Johnson", "Alice Williams", "Michael Brown"];
        const mockStreets = ["123 Broadway Rd", "456 Oak Avenue", "789 Pine Street", "321 Elm Lane", "555 Cedar Blvd"];
        const mockCities = ["New York, NY 10001", "Los Angeles, CA 90012", "Chicago, IL 60605", "Houston, TX 77002", "Phoenix, AZ 85003"];
        
        const randomName = mockNames[Math.floor(Math.random() * mockNames.length)];
        const randomStreet = mockStreets[Math.floor(Math.random() * mockStreets.length)];
        const randomCity = mockCities[Math.floor(Math.random() * mockCities.length)];

        document.getElementById('genActionsBar').style.display = 'flex';
        resultBox.style.display = 'block';
        resultBox.innerHTML = `
            <div style="color:#00ff66; font-weight:bold; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:5px;">
                <i class="fa-solid fa-gear"></i> GENERATED PROFILES (${amount})
            </div>
            <strong>Billing Name:</strong> ${randomName}<br>
            <strong>Billing Address:</strong> ${randomStreet}, ${randomCity}<br>
            <strong>Billing Phone:</strong> +1-202-555-${Math.floor(1000 + Math.random() * 8999)}<br><br>
            <strong>Card Strings:</strong>
            ${generatedCardsHTML}
        `;
        logMessage(`CC generator tool run. BIN Prefix: ${binPrefix}, Amount: ${amount}`);
    });

    document.getElementById('copyGenCardsBtn').addEventListener('click', () => {
        if (lastGeneratedCards.length === 0) return;
        navigator.clipboard.writeText(lastGeneratedCards.join('\n'));
        showToast("Copied all generated cards to clipboard!");
    });

    document.getElementById('regenCardsBtn').addEventListener('click', () => {
        document.getElementById('runCcGeneratorBtn').click();
    });
}

// BASE64 TOOL ENGINE
if (document.getElementById('runB64EncodeBtn')) {
    document.getElementById('runB64EncodeBtn').addEventListener('click', () => {
        const input = document.getElementById('b64Input').value;
        try {
            document.getElementById('b64Output').value = btoa(input);
            logMessage("Base64 encoding executed.");
        } catch (err) {
            showToast("Invalid string characters for Base64 encoding", "error");
        }
    });
    document.getElementById('runB64DecodeBtn').addEventListener('click', () => {
        const input = document.getElementById('b64Input').value;
        try {
            document.getElementById('b64Output').value = atob(input);
            logMessage("Base64 decoding executed.");
        } catch (err) {
            showToast("Could not decode string. Verify base64 signature format.", "error");
        }
    });
}

// ------------------ CHECKOUT WIZARD PROCESS ------------------
let timerInterval;

function startCryptoCountdown() {
    let duration = 600; // 10 minutes
    const timerEl = document.getElementById('cryptoTimer');
    if (!timerEl) return;
    
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        let minutes = Math.floor(duration / 60);
        let seconds = duration % 60;
        minutes = minutes < 10 ? '0' + minutes : minutes;
        seconds = seconds < 10 ? '0' + seconds : seconds;

        timerEl.textContent = `${minutes}:${seconds}`;

        if (--duration < 0) {
            clearInterval(timerInterval);
            timerEl.textContent = "EXPIRED";
            logMessage("Crypto payment session expired.", "ERROR");
        }
    }, 1000);
}

// Checkout button click
if (document.getElementById('checkoutBtn')) {
    document.getElementById('checkoutBtn').addEventListener('click', () => {
        if (cart.length === 0) {
            showToast("Cart is currently empty.", "error");
            return;
        }
        document.getElementById('cartDrawer').classList.remove('open');
        
        // Populate step 1 review items
        const checkoutCartList = document.getElementById('checkoutCartItems');
        checkoutCartList.innerHTML = '';
        cart.forEach(item => {
            const div = document.createElement('div');
            div.style = 'display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.02); padding:10px 15px; border-radius:8px; margin-bottom:10px; border:1px solid var(--border-color);';
            div.innerHTML = `
                <div>
                    <strong style="font-size:13px; color:#fff;">${item.name}</strong><br>
                    <span style="font-size:11px; color:var(--text-muted);">${item.brand} | BIN: ${item.bin}</span>
                </div>
                <span style="font-family:var(--font-mono); color:var(--primary); font-size:13px;">$${item.price}</span>
            `;
            checkoutCartList.appendChild(div);
        });

        resetWizardIndicators(1);
        showWizardStep(1);
        document.getElementById('checkoutModal').classList.add('active');
        logMessage("Order checkout wizard initiated.");
    });
}

function resetWizardIndicators(stepNo) {
    for (let i = 1; i <= 3; i++) {
        const ind = document.getElementById(`stepIndicator${i}`);
        if (ind) {
            ind.className = 'wizard-step';
            if (i < stepNo) ind.classList.add('completed');
            if (i === stepNo) ind.classList.add('active');
        }
    }
}

function showWizardStep(stepNo) {
    const s1 = document.getElementById('checkoutStep1');
    if (!s1) return;
    s1.style.display = stepNo === 1 ? 'block' : 'none';
    document.getElementById('checkoutStep2').style.display = stepNo === 2 ? 'block' : 'none';
    document.getElementById('checkoutStep3').style.display = stepNo === 3 ? 'block' : 'none';
}

if (document.getElementById('goToStep2Btn')) {
    document.getElementById('goToStep2Btn').addEventListener('click', () => {
        resetWizardIndicators(2);
        showWizardStep(2);
        logMessage("Checkout wizard progressed to Step 2.");
    });

    document.getElementById('backToStep1Btn').addEventListener('click', () => {
        resetWizardIndicators(1);
        showWizardStep(1);
    });

    document.getElementById('goToStep3Btn').addEventListener('click', () => {
        const email = document.getElementById('checkoutEmail').value.trim();
        if (!email) {
            showToast("Please enter a valid email.", "error");
            return;
        }
        resetWizardIndicators(3);
        showWizardStep(3);
        startCryptoCountdown();
        simulatePaymentLogs();
        logMessage("Checkout wizard progressed to Step 3.");
    });

    document.getElementById('backToStep2Btn').addEventListener('click', () => {
        resetWizardIndicators(2);
        showWizardStep(2);
    });


}

let logTimeout1, logTimeout2, logTimeout3;
function simulatePaymentLogs() {
    const consoleEl = document.getElementById('checkoutConsole');
    if (!consoleEl) return;
    consoleEl.innerHTML = "[SYSTEM] Monero/Bitcoin RPC Daemon connection established.<br>[RPC] Monitoring transaction mempools...";
    
    clearTimeout(logTimeout1);
    clearTimeout(logTimeout2);
    clearTimeout(logTimeout3);

    logTimeout1 = setTimeout(() => {
        consoleEl.innerHTML += "<br><span style='color:#00ff66;'>[MEMPOOL] Detected unconfirmed tx for 0.0014 BTC...</span>";
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }, 3000);

    logTimeout2 = setTimeout(() => {
        consoleEl.innerHTML += "<br>[BLOCKCHAIN] Validating transaction block depth (1/3 confirmations)...";
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }, 6000);

    logTimeout3 = setTimeout(() => {
        consoleEl.innerHTML += "<br><span style='color:var(--primary);'>[PAYMENT] Confirmations 3/3 reached. Funds received!</span>";
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }, 9000);
}

// Wallet UI Updates
function updateWalletUI() {
    const headerBal = document.getElementById('walletBalanceText');
    const modalBal = document.getElementById('walletModalBalance');
    const wizardBal = document.getElementById('wizardWalletBalanceText');
    
    // Refresh userBalance from localStorage in case it changed in admin panel
    userBalance = parseFloat(localStorage.getItem('nexus_balance')) || 0.00;
    
    const formatted = `$${userBalance.toFixed(2)}`;
    if (headerBal) headerBal.textContent = formatted;
    if (modalBal) modalBal.textContent = formatted;
    if (wizardBal) wizardBal.textContent = formatted;
}

// Final Confirm Purchase Wizard Trigger
if (document.getElementById('confirmPaymentWizardBtn')) {
    document.getElementById('confirmPaymentWizardBtn').addEventListener('click', () => {
        const total = cart.reduce((sum, item) => sum + item.price, 0);
        
        // Check if Pay with Wallet is active
        const isWalletPay = document.getElementById('wizardWalletBtn').classList.contains('active');
        
        if (isWalletPay) {
            if (userBalance < total) {
                showToast("Insufficient Wallet Balance. Please deposit crypto and send SS to @damxd89.", "error");
                logMessage(`Checkout failed: Insufficient wallet balance ($${userBalance.toFixed(2)} / $${total.toFixed(2)}).`, "ERROR");
                return;
            }
            
            // Deduct balance
            userBalance -= total;
            persistState();
            updateWalletUI();
        } else {
            // Crypto deposit tab is active
            showToast("Payment Pending. Transfer crypto and send transaction screenshot to @damxd89 on Telegram.", "error");
            logMessage(`Checkout pending: Awaiting manual transfer confirmation for $${total.toFixed(2)}.`, "WARNING");
            return;
        }

        const invoiceNo = Math.floor(Math.random() * 899999) + 100000;
        const txHash = '0x' + Array.from({length: 40}, () => Math.floor(Math.random()*16).toString(16)).join('');
        const email = document.getElementById('checkoutEmail').value.trim();

        // Generate unlocked card details
        const generatedItems = cart.map(item => {
            const randomFullNum = `${item.bin}${Math.floor(1000000000 + Math.random() * 9000000000)}`;
            const randomExpMonth = String(Math.floor(Math.random() * 12) + 1).padStart(2, '0');
            const randomExpYear = Math.floor(Math.random() * 5) + 29;
            const randomCvv = Math.floor(100 + Math.random() * 899);
            return {
                name: item.name,
                brand: item.brand,
                bin: item.bin,
                cardNumber: randomFullNum,
                expiry: `${randomExpMonth}/${randomExpYear}`,
                cvv: randomCvv,
                billingName: item.billingName,
                billingAddress: item.billingAddress,
                billingCityStateZip: item.billingCityStateZip,
                billingPhone: item.billingPhone
            };
        });

        let unlockedItemsHTML = generatedItems.map(item => `
            <div style="border-bottom:1px solid rgba(255,255,255,0.05); padding:10px 0; margin-bottom:10px;">
                <strong>${item.name} (${item.brand})</strong><br>
                Card Number: <span style="color:var(--primary); font-weight:bold;">${item.cardNumber}</span><br>
                Expiry: <span style="color:#00ff66;">${item.expiry}</span> | CVV: <span style="color:#ff4a6e;">${item.cvv}</span><br>
                <strong style="color:var(--text-muted); font-size:10px;">BILLING INFORMATION:</strong><br>
                Name: ${item.billingName}<br>
                Address: ${item.billingAddress}, ${item.billingCityStateZip}<br>
                Phone: ${item.billingPhone}
            </div>
        `).join('');

        const receiptHTML = `
            <div style="border-bottom:1px dashed var(--border-color); padding-bottom:12px; margin-bottom:12px;">
                <strong>INVOICE NO:</strong> #${invoiceNo}<br>
                <strong>TIMESTAMP:</strong> ${new Date().toLocaleString()}<br>
                <strong>DELIVERED TO:</strong> ${email}<br>
                <strong>TX STATUS:</strong> UNLOCKED / SUCCESSFUL
            </div>
            <div style="margin-bottom:12px;">
                <strong>UNLOCKED CARD & BILLING DATA:</strong><br>
                ${unlockedItemsHTML}
            </div>
            <div style="border-top:1px dashed var(--border-color); padding-top:12px;">
                <strong>TOTAL DEDUCTED:</strong> $${total.toFixed(2)}<br>
                <strong>BLOCKCHAIN HASH:</strong><br>
                <span style="font-size:9.5px; word-break:break-all; color:var(--primary);">${txHash}</span>
            </div>
        `;

        document.getElementById('invoiceDetails').innerHTML = receiptHTML;

        // Push into global persistent orders
        const newOrder = {
            id: invoiceNo,
            username: sessionDetails ? sessionDetails.username : 'Buyer',
            timestamp: new Date().toLocaleString(),
            total: total,
            txHash: txHash,
            items: generatedItems
        };
        orders.unshift(newOrder);

        // Update stats
        salesStats.totalRevenue += total;
        salesStats.countSold += cart.length;

        cart = [];
        persistState();
        updateCartUI();

        clearInterval(timerInterval);
        closeModal('checkoutModal');
        document.getElementById('receiptModal').classList.add('active');
        showToast("Purchase completed!");
        logMessage(`Checkout success. Invoice #${invoiceNo} issued for $${total}.`);
    });
}

if (document.getElementById('closeReceiptBtn')) {
    document.getElementById('closeReceiptBtn').addEventListener('click', () => {
        closeModal('receiptModal');
        renderStore();
    });
}

// ------------------ BUYER ORDER DASHBOARD RENDERING ------------------
function renderOrdersDashboard() {
    const container = document.getElementById('ordersListContainer');
    if (!container) return;
    container.innerHTML = '';

    const currentUsername = sessionDetails ? sessionDetails.username : 'Buyer';
    const userOrders = orders.filter(o => o.username.toLowerCase() === currentUsername.toLowerCase());

    if (userOrders.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-dim); padding: 40px 0;">
                <i class="fa-solid fa-receipt" style="font-size: 40px; margin-bottom: 15px;"></i>
                <p>No card credentials unlocked yet.</p>
            </div>
        `;
        return;
    }

    userOrders.forEach(order => {
        const div = document.createElement('div');
        div.className = 'detail-card-panel';
        div.style.marginBottom = '20px';
        div.style.background = 'rgba(255,255,255,0.01)';
        div.style.boxShadow = 'var(--neo-shadow-out)';

        let itemsHTML = order.items.map(item => `
            <div style="border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px; margin-top: 12px; font-size:12px;">
                <strong>${item.name} (${item.brand})</strong><br>
                Card Number: <span style="color:var(--primary); font-family:var(--font-mono); font-weight:bold;">${item.cardNumber}</span><br>
                Expiry: <span style="color:#00ff66;">${item.expiry}</span> | CVV: <span style="color:#ff4a6e;">${item.cvv}</span><br>
                <strong style="color:var(--text-muted); font-size:9.5px; display:block; margin-top:4px;">BILLING INFORMATION:</strong>
                Name: ${item.billingName}<br>
                Address: ${item.billingAddress}, ${item.billingCityStateZip}<br>
                Phone: ${item.billingPhone}
            </div>
        `).join('');

        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:8px; margin-bottom:8px;">
                <strong style="color:#fff;">Invoice #${order.id}</strong>
                <span style="font-size:11px; color:var(--text-muted);">${order.timestamp}</span>
            </div>
            <div style="font-size:11px; color:var(--text-muted);">
                <strong>Total Paid:</strong> $${order.total.toFixed(2)}<br>
                <strong>TX hash:</strong> <span style="font-family:var(--font-mono); color:var(--primary); font-size:9px; word-break:break-all;">${order.txHash}</span>
            </div>
            ${itemsHTML}
        `;
        container.appendChild(div);
    });
}

// ------------------ LUHN VALIDATOR & STRIPE CHECK SIMULATOR ------------------
function jsLuhnCheck(num) {
    const digits = num.split('').map(Number);
    let sum = 0;
    const parity = digits.length % 2;
    for (let i = 0; i < digits.length; i++) {
        let d = digits[i];
        if (i % 2 === parity) {
            d *= 2;
            if (d > 9) d -= 9;
        }
        sum += d;
    }
    return sum % 10 === 0;
}

if (document.getElementById('runCardCheckerBtn')) {
    document.getElementById('runCardCheckerBtn').addEventListener('click', async () => {
        const cardInput = document.getElementById('checkerCardStr').value.trim();
        const approvedBox = document.getElementById('checkerApprovedList');
        const declinedBox = document.getElementById('checkerDeclinedList');
        
        if (!cardInput) {
            showToast("Please enter card details.", "error");
            return;
        }
        
        const lines = cardInput.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        if (lines.length === 0) return;
        
        approvedBox.value = '';
        declinedBox.value = '';
        
        for (let cardLine of lines) {
            const parts = cardLine.split('|');
            const ccNum = parts[0] ? parts[0].replace(/\D/g, '') : '';
            
            if (ccNum.length < 15 || ccNum.length > 19) {
                declinedBox.value += `${cardLine}\n`;
                continue;
            }
            
            // 1. Luhn Check
            const luhnPassed = jsLuhnCheck(ccNum);
            if (!luhnPassed) {
                declinedBox.value += `${cardLine}\n`;
                continue;
            }
            
            // Short artificial latency delay to simulate TLS check
            await new Promise(r => setTimeout(r, 400));
            
            const approved = Math.random() > 0.45;
            if (approved) {
                approvedBox.value += `${cardLine}\n`;
                logMessage(`Bulk Check: Card Approved - ${ccNum.substring(0, 6)}...`);
            } else {
                declinedBox.value += `${cardLine}\n`;
                logMessage(`Bulk Check: Card Declined - ${ccNum.substring(0, 6)}...`, "WARNING");
            }
        }
        
        showToast("Bulk card verification finished!");
    });
}

// Bind filter listeners always (not gated on openCartBtn)
if (document.getElementById('searchInput')) {
    document.getElementById('searchInput').addEventListener('input', renderStore);
    document.getElementById('brandFilter').addEventListener('change', renderStore);
    document.getElementById('tierFilter').addEventListener('change', renderStore);
    document.getElementById('sortControl').addEventListener('change', renderStore);

    document.getElementById('resetFiltersBtn').addEventListener('click', () => {
        document.getElementById('searchInput').value = '';
        document.getElementById('brandFilter').value = 'all';
        document.getElementById('tierFilter').value = 'all';
        document.getElementById('sortControl').value = 'default';
        renderStore();
        showToast('Search filters reset to default.');
        logMessage('Filters and sorts reset to default values.');
    });
}

if (document.getElementById('openCartBtn')) {
    document.getElementById('openCartBtn').addEventListener('click', () => {
        document.getElementById('cartDrawer').classList.add('open');
        logMessage('Shopping cart panel drawer opened.');
    });

    document.getElementById('closeCartBtn').addEventListener('click', () => {
        document.getElementById('cartDrawer').classList.remove('open');
    });

    document.getElementById('closeCheckoutBtn').addEventListener('click', () => closeModal('checkoutModal'));
    document.getElementById('closeDetailBtn').addEventListener('click', () => closeModal('detailModal'));
}

// Bind Buyer Dashboard and Wallet Modals
document.addEventListener('DOMContentLoaded', () => {
    // Initial render of store cards and cart
    renderStore();
    updateCartUI();

    // Initial balance render
    updateWalletUI();

    const openOrdersBtn = document.getElementById('openOrdersBtn');
    if (openOrdersBtn) {
        openOrdersBtn.addEventListener('click', () => {
            renderOrdersDashboard();
            document.getElementById('ordersModal').classList.add('active');
            logMessage("Buyer purchase dashboard modal opened.");
        });
    }

    const closeOrdersBtn = document.getElementById('closeOrdersBtn');
    if (closeOrdersBtn) {
        closeOrdersBtn.addEventListener('click', () => {
            closeModal('ordersModal');
        });
    }

    const openStripeAutoBtn = document.getElementById('openStripeAutoBtn');
    if (openStripeAutoBtn) {
        openStripeAutoBtn.addEventListener('click', () => {
            window.open('https://t.me/newthingsneverbot', '_blank');
        });
    }

    // --- WALLET MODAL EVENTS ---
    const openWalletBtn = document.getElementById('openWalletBtn');
    if (openWalletBtn) {
        openWalletBtn.addEventListener('click', () => {
            updateWalletUI();
            document.getElementById('walletModal').classList.add('active');
            logMessage("Wallet modal panel opened.");
        });
    }

    const closeWalletBtn = document.getElementById('closeWalletBtn');
    if (closeWalletBtn) {
        closeWalletBtn.addEventListener('click', () => {
            closeModal('walletModal');
        });
    }

    // Deposit Tabs switching
    const depTabUsdt = document.getElementById('depositTabUsdt');
    const depTabBtc = document.getElementById('depositTabBtc');
    const depUsdtArea = document.getElementById('depositUsdtArea');
    const depBtcArea = document.getElementById('depositBtcArea');

    if (depTabUsdt && depTabBtc) {
        depTabUsdt.addEventListener('click', () => {
            depTabUsdt.classList.add('active');
            depTabBtc.classList.remove('active');
            depUsdtArea.style.display = 'block';
            depBtcArea.style.display = 'none';
        });

        depTabBtc.addEventListener('click', () => {
            depTabBtc.classList.add('active');
            depTabUsdt.classList.remove('active');
            depUsdtArea.style.display = 'none';
            depBtcArea.style.display = 'block';
        });
    }

    // Copy handlers
    const copyAddr = (inputId) => {
        const input = document.getElementById(inputId);
        if (input) {
            input.select();
            navigator.clipboard.writeText(input.value);
            showToast("Address copied to clipboard!");
            logMessage(`Copied address from ${inputId} input.`);
        }
    };

    if (document.getElementById('copyUsdtBtn')) {
        document.getElementById('copyUsdtBtn').addEventListener('click', () => copyAddr('usdtAddressInput'));
    }
    if (document.getElementById('copyBtcBtn')) {
        document.getElementById('copyBtcBtn').addEventListener('click', () => copyAddr('btcAddressInput'));
    }

    // --- CHECKOUT WIZARD TABS ---
    const wizardWalletBtn = document.getElementById('wizardWalletBtn');
    const wizardCryptoBtn = document.getElementById('wizardCryptoBtn');
    const wizardWalletArea = document.getElementById('wizardWalletArea');
    const wizardCryptoArea = document.getElementById('wizardCryptoArea');

    if (wizardWalletBtn && wizardCryptoBtn) {
        wizardWalletBtn.addEventListener('click', () => {
            wizardWalletBtn.classList.add('active');
            wizardCryptoBtn.classList.remove('active');
            wizardWalletArea.style.display = 'block';
            wizardCryptoArea.style.display = 'none';
            // Force verify update
            updateWalletUI();
        });

        wizardCryptoBtn.addEventListener('click', () => {
            wizardCryptoBtn.classList.add('active');
            wizardWalletBtn.classList.remove('active');
            wizardWalletArea.style.display = 'none';
            wizardCryptoArea.style.display = 'block';
        });
    }

    // Wizard Crypto Sub-tabs switching
    const wizardUsdtTab = document.getElementById('wizardUsdtTab');
    const wizardBtcTab = document.getElementById('wizardBtcTab');
    const wizardUsdtArea = document.getElementById('wizardUsdtArea');
    const wizardBtcArea = document.getElementById('wizardBtcArea');

    if (wizardUsdtTab && wizardBtcTab) {
        wizardUsdtTab.addEventListener('click', () => {
            wizardUsdtTab.classList.add('active');
            wizardBtcTab.classList.remove('active');
            wizardUsdtArea.style.display = 'block';
            wizardBtcArea.style.display = 'none';
        });

        wizardBtcTab.addEventListener('click', () => {
            wizardBtcTab.classList.add('active');
            wizardUsdtTab.classList.remove('active');
            wizardUsdtArea.style.display = 'none';
            wizardBtcArea.style.display = 'block';
        });
    }

    if (document.getElementById('wizardCopyUsdtBtn')) {
        document.getElementById('wizardCopyUsdtBtn').addEventListener('click', () => copyAddr('wizardUsdtInput'));
    }
    if (document.getElementById('wizardCopyBtcBtn')) {
        document.getElementById('wizardCopyBtcBtn').addEventListener('click', () => copyAddr('wizardBtcInput'));
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('nexus_session');
            window.location.href = '/login';
        });
    }
});
