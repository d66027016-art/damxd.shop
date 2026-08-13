// Shared Lists Preloads
const initialProducts = [
    { id: 1, name: "Visa Classic Standard", brand: "Visa", tier: "Classic", bin: "411132", country: "US", limit: 1500, price: 25, health: 96, desc: "High balance limit, United States issued.", billingName: "James Carter", billingAddress: "742 Evergreen Terrace", billingCityStateZip: "Springfield, OR 97477", billingPhone: "+1-541-555-0199" },
    { id: 2, name: "Mastercard Gold Premium", brand: "Mastercard", tier: "Gold", bin: "541275", country: "DE", limit: 4500, price: 40, health: 94, desc: "Premium Gold Class, Germany region limit check cleared.", billingName: "Maximilian Schulz", billingAddress: "Kaiserstraße 45", billingCityStateZip: "Frankfurt 60311", billingPhone: "+49-69-555-4321" },
    { id: 3, name: "Amex Platinum Premium", brand: "Amex", tier: "Platinum", bin: "378282", country: "US", limit: 12000, price: 75, health: 99, desc: "Business Class Platinum Card, worldwide valid.", billingName: "Elizabeth Stone", billingAddress: "58 Park Avenue", billingCityStateZip: "New York, NY 10016", billingPhone: "+1-212-555-8732" },
    { id: 4, name: "Discover Classic Fresh", brand: "Discover", tier: "Classic", bin: "601138", country: "US", limit: 2500, price: 30, health: 91, desc: "US region card, freshly updated.", billingName: "David Miller", billingAddress: "1024 Blue Sky Rd", billingCityStateZip: "Denver, CO 80202", billingPhone: "+1-303-555-0144" },
    { id: 5, name: "Visa Business Platinum", brand: "Visa", tier: "Platinum", bin: "482811", country: "FR", limit: 18000, price: 55, health: 98, desc: "Corporate card limit, high balance validation.", billingName: "Jean Dupont", billingAddress: "12 Rue de la Paix", billingCityStateZip: "Paris 75002", billingPhone: "+33-1-555-9876" },
    { id: 6, name: "Mastercard Black Infinite", brand: "Mastercard", tier: "Black", bin: "522199", country: "UK", limit: 35000, price: 90, health: 97, desc: "Ultra premium black edition card, verified.", billingName: "Arthur Pendelton", billingAddress: "88 Baker Street", billingCityStateZip: "London NW1 6XE", billingPhone: "+44-20-7946-0958" }
];

// State Manager
let products = JSON.parse(localStorage.getItem('nexus_products')) || initialProducts;
let cart = JSON.parse(localStorage.getItem('nexus_cart')) || [];
let salesStats = JSON.parse(localStorage.getItem('nexus_sales_stats')) || { totalRevenue: 1380, countSold: 28 };

// Connection Gateways Configuration
const defaultConnection = {
    activeNode: "Primary Gateway",
    latency: 32,
    protocol: "SSL/TLS",
    peers: 14,
    nodesList: [
        { name: "Primary Gateway", protocol: "SSL/TLS", minLatency: 25, maxLatency: 45, basePeers: 12 },
        { name: "Backup Node", protocol: "Secure Mirror", minLatency: 60, maxLatency: 95, basePeers: 8 },
        { name: "Tor Onion Route", protocol: "End-to-End PGP", minLatency: 120, maxLatency: 195, basePeers: 22 }
    ]
};
let connectionState = JSON.parse(localStorage.getItem('nexus_connection')) || defaultConnection;
let orders = JSON.parse(localStorage.getItem('nexus_orders')) || [];
let userBalance = parseFloat(localStorage.getItem('nexus_balance')) || 0.00;

// Save State
function persistState() {
    localStorage.setItem('nexus_products', JSON.stringify(products));
    localStorage.setItem('nexus_cart', JSON.stringify(cart));
    localStorage.setItem('nexus_sales_stats', JSON.stringify(salesStats));
    localStorage.setItem('nexus_connection', JSON.stringify(connectionState));
    localStorage.setItem('nexus_orders', JSON.stringify(orders));
    localStorage.setItem('nexus_balance', userBalance);
}

// ------------------ API CONSOLE LOGGER ------------------
function logMessage(text, type = 'INFO') {
    const logsContainer = document.getElementById('consoleLogs');
    if (!logsContainer) return;
    const time = new Date().toLocaleTimeString();
    const logRow = document.createElement('div');
    logRow.innerHTML = `<span style="color:var(--text-dim);">[${time}]</span> <span style="color:${type === 'ERROR' ? '#ff0844' : '#00f2fe'}; font-weight:bold;">[${type}]</span> ${text}`;
    logsContainer.appendChild(logRow);
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

// ------------------ TOAST ALERTS ------------------
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast-msg ${type === 'success' ? 'success' : 'error'}`;
    toast.innerHTML = `<i class="${type === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
        setTimeout(() => toast.remove(), 400);
    }, 3000);
}
