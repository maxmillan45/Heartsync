// Additional JavaScript utilities for profile page
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `fixed top-20 right-4 px-6 py-3 rounded-lg shadow-lg z-50 animate-fade-in ${
        type === 'success' ? 'bg-green-500' : 'bg-red-500'
    } text-white font-medium`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add any other utility functions you need