// Prepopulated default accounts
const defaultUsers = [
    { username: "admin", password: "admin", role: "admin" },
    { username: "buyer", password: "buyer", role: "buyer" }
];

let users = JSON.parse(localStorage.getItem('nexus_users')) || defaultUsers;
if (!localStorage.getItem('nexus_users')) {
    localStorage.setItem('nexus_users', JSON.stringify(users));
}

// Redirect if already logged in
const currentSession = JSON.parse(localStorage.getItem('nexus_session'));
if (currentSession && document.getElementById('loginForm')) {
    if (currentSession.role === 'admin') {
        window.location.href = '/admin';
    } else {
        window.location.href = '/';
    }
}

// Tab Swapping
if (document.getElementById('tabLoginBtn')) {
    document.getElementById('tabLoginBtn').addEventListener('click', function() {
        toggleTab(this, 'loginForm', 'registerForm');
    });
    document.getElementById('tabRegisterBtn').addEventListener('click', function() {
        toggleTab(this, 'registerForm', 'loginForm');
    });
}

function toggleTab(tabEl, showId, hideId) {
    document.querySelectorAll('.auth-tabs .tab-btn').forEach(btn => btn.classList.remove('active'));
    tabEl.classList.add('active');
    document.getElementById(showId).style.display = 'block';
    document.getElementById(hideId).style.display = 'none';
}

// Login Handler
if (document.getElementById('loginForm')) {
    document.getElementById('loginForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const usernameInput = document.getElementById('loginUser').value.trim();
        const passwordInput = document.getElementById('loginPass').value;

        const foundUser = users.find(u => u.username.toLowerCase() === usernameInput.toLowerCase() && u.password === passwordInput);
        if (foundUser) {
            localStorage.setItem('nexus_session', JSON.stringify({
                username: foundUser.username,
                role: foundUser.role
            }));
            showToast("Authorized. Redirecting...", "success");
            setTimeout(() => {
                if (foundUser.role === 'admin') {
                    window.location.href = '/admin';
                } else {
                    window.location.href = '/';
                }
            }, 800);
        } else {
            showToast("Access Denied. Check credentials.", "error");
        }
    });
}

// Helper to generate 10 recovery codes
function generateRecoveryCodes() {
    const codes = [];
    for (let i = 0; i < 10; i++) {
        const num = Math.floor(1000 + Math.random() * 9000);
        codes.push(`DAMXD-${num}`);
    }
    return codes;
}

// Register Handler
if (document.getElementById('registerForm')) {
    document.getElementById('registerForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const usernameInput = document.getElementById('regUser').value.trim();
        const passwordInput = document.getElementById('regPass').value;
        const roleInput = 'buyer';

        const userExists = users.some(u => u.username.toLowerCase() === usernameInput.toLowerCase());
        if (userExists) {
            showToast("Username already registered.", "error");
            return;
        }

        const generatedCodes = generateRecoveryCodes();
        const newUser = {
            username: usernameInput,
            password: passwordInput,
            role: roleInput,
            recoveryCodes: generatedCodes
        };

        users.push(newUser);
        localStorage.setItem('nexus_users', JSON.stringify(users));

        // Show the recovery codes modal
        const codesTextarea = document.getElementById('recoveryCodesList');
        if (codesTextarea) {
            codesTextarea.value = generatedCodes.join('\n');
        }
        
        const modal = document.getElementById('recoveryCodesModal');
        if (modal) {
            modal.classList.add('active');
        }

        // Setup copy button
        const copyBtn = document.getElementById('copyRecoveryCodesBtn');
        if (copyBtn) {
            copyBtn.onclick = () => {
                codesTextarea.select();
                navigator.clipboard.writeText(codesTextarea.value);
                showToast("Codes copied to clipboard!");
            };
        }

        // Setup close button to redirect
        const closeBtn = document.getElementById('closeRecoveryModalBtn');
        if (closeBtn) {
            closeBtn.onclick = () => {
                modal.classList.remove('active');
                localStorage.setItem('nexus_session', JSON.stringify({
                    username: newUser.username,
                    role: newUser.role
                }));
                showToast("Authorized. Redirecting...", "success");
                setTimeout(() => {
                    if (newUser.role === 'admin') {
                        window.location.href = '/admin';
                    } else {
                        window.location.href = '/';
                    }
                }, 800);
            };
        }
    });
}

// Forgot Password / Recovery switcher
if (document.getElementById('forgotPasswordLink')) {
    document.getElementById('forgotPasswordLink').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('loginForm').style.display = 'none';
        if (document.getElementById('registerForm')) document.getElementById('registerForm').style.display = 'none';
        document.getElementById('recoverForm').style.display = 'block';
        document.querySelector('.auth-tabs').style.display = 'none';
    });
}

if (document.getElementById('backToLoginLink')) {
    document.getElementById('backToLoginLink').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('loginForm').style.display = 'block';
        document.getElementById('recoverForm').style.display = 'none';
        document.querySelector('.auth-tabs').style.display = 'flex';
        document.getElementById('tabLoginBtn').click();
    });
}

// Recover Form Submission
if (document.getElementById('recoverForm')) {
    document.getElementById('recoverForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const userVal = document.getElementById('recoverUser').value.trim();
        const codeVal = document.getElementById('recoverCode').value.trim().toUpperCase();
        const newPassVal = document.getElementById('recoverNewPass').value;

        const user = users.find(u => u.username.toLowerCase() === userVal.toLowerCase());
        if (!user) {
            showToast("Username not found.", "error");
            return;
        }

        // Make sure user has recoveryCodes array
        if (!user.recoveryCodes || !Array.isArray(user.recoveryCodes)) {
            showToast("No recovery codes set up for this user.", "error");
            return;
        }

        const codeIndex = user.recoveryCodes.indexOf(codeVal);
        if (codeIndex === -1) {
            showToast("Invalid or already used recovery code.", "error");
            return;
        }

        // Consume the code
        user.recoveryCodes.splice(codeIndex, 1);
        
        // Update password
        user.password = newPassVal;

        // Save users
        localStorage.setItem('nexus_users', JSON.stringify(users));

        showToast("Password reset successful! Logging in...", "success");

        // Log in immediately
        localStorage.setItem('nexus_session', JSON.stringify({
            username: user.username,
            role: user.role
        }));

        setTimeout(() => {
            if (user.role === 'admin') {
                window.location.href = '/admin';
            } else {
                window.location.href = '/';
            }
        }, 800);
    });
}
