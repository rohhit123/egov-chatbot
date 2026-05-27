// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    // Create hamburger menu button
    const navbar = document.querySelector('.navbar');
    const navLinks = document.querySelector('.nav-links');
    
    if (navbar && navLinks && window.innerWidth <= 768) {
        const menuBtn = document.createElement('button');
        menuBtn.className = 'mobile-menu-btn';
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        menuBtn.onclick = function() {
            navLinks.classList.toggle('show');
        };
        navbar.insertBefore(menuBtn, navbar.firstChild);
    }
    
    // Auto-hide flash messages
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Chat scrolling to bottom
function scrollToBottom() {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Handle window resize
window.addEventListener('resize', function() {
    const navLinks = document.querySelector('.nav-links');
    const menuBtn = document.querySelector('.mobile-menu-btn');
    
    if (window.innerWidth > 768) {
        if (menuBtn) menuBtn.remove();
        if (navLinks) navLinks.classList.remove('show');
    } else if (!menuBtn && navLinks) {
        const navbar = document.querySelector('.navbar');
        const newMenuBtn = document.createElement('button');
        newMenuBtn.className = 'mobile-menu-btn';
        newMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        newMenuBtn.onclick = function() {
            navLinks.classList.toggle('show');
        };
        navbar.insertBefore(newMenuBtn, navbar.firstChild);
    }
});