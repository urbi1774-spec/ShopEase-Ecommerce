/**
 * ShopEase - Core UI, Toast Notifications, Confirmation Modals & Validation
 */

window.ShopEase = {
    showToast(message, type = 'success') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const iconMap = {
            success: 'fa-circle-check',
            error: 'fa-circle-exclamation',
            warning: 'fa-triangle-exclamation',
            info: 'fa-circle-info'
        };
        const colorMap = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#2563eb'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div style="display:flex;align-items:center;gap:0.75rem;">
                <i class="fa-solid ${iconMap[type] || iconMap.info}" style="color:${colorMap[type] || colorMap.info};font-size:1.2rem;"></i>
                <span style="font-size:0.92rem;font-weight:600;color:#0f172a;">${message}</span>
            </div>
            <button type="button" aria-label="Close notification" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:1rem;">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;

        toast.querySelector('button').addEventListener('click', () => {
            toast.remove();
        });

        container.appendChild(toast);

        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(30px)';
                toast.style.transition = 'all 0.25s ease';
                setTimeout(() => toast.remove(), 250);
            }
        }, 4200);
    },

    confirmAction(title, message, onConfirm) {
        const modal = document.getElementById('confirm-modal');
        if (!modal) {
            if (window.confirm(message)) onConfirm();
            return;
        }
        document.getElementById('confirm-modal-title').textContent = title;
        document.getElementById('confirm-modal-message').textContent = message;
        modal.classList.add('active');

        const yesBtn = document.getElementById('confirm-modal-yes');
        const noBtn = document.getElementById('confirm-modal-no');

        const cleanup = () => {
            modal.classList.remove('active');
            yesBtn.replaceWith(yesBtn.cloneNode(true));
            noBtn.replaceWith(noBtn.cloneNode(true));
        };

        document.getElementById('confirm-modal-yes').addEventListener('click', () => {
            cleanup();
            onConfirm();
        });

        document.getElementById('confirm-modal-no').addEventListener('click', () => {
            cleanup();
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Sticky Navbar shadow on scroll
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 12) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }

    // Mobile Menu Toggle
    const mobileBtn = document.getElementById('mobile-menu-toggle');
    const navLinks = document.getElementById('nav-links');
    if (mobileBtn && navLinks) {
        mobileBtn.addEventListener('click', () => {
            navLinks.classList.toggle('open');
        });
    }

    // Auto-dismiss server-flashed toasts
    document.querySelectorAll('.server-toast').forEach((el) => {
        const msg = el.getAttribute('data-message');
        const category = el.getAttribute('data-category') || 'info';
        if (msg) {
            window.ShopEase.showToast(msg, category);
        }
    });

    // Confirmation dialog handler for forms/buttons with data-confirm
    document.querySelectorAll('form[data-confirm]').forEach((form) => {
        form.addEventListener('submit', (e) => {
            if (form.dataset.confirmed === 'true') return;
            e.preventDefault();
            const title = form.getAttribute('data-confirm-title') || 'Confirm Action';
            const message = form.getAttribute('data-confirm');
            window.ShopEase.confirmAction(title, message, () => {
                form.dataset.confirmed = 'true';
                form.submit();
            });
        });
    });

    // Quantity increment/decrement buttons on product detail page
    document.querySelectorAll('[data-qty-control]').forEach((wrapper) => {
        const input = wrapper.querySelector('.qty-input');
        const decBtn = wrapper.querySelector('[data-qty-dec]');
        const incBtn = wrapper.querySelector('[data-qty-inc]');
        if (!input) return;

        const maxStock = parseInt(input.getAttribute('max') || '99', 10);

        if (decBtn) {
            decBtn.addEventListener('click', () => {
                const current = parseInt(input.value || '1', 10);
                if (current > 1) input.value = current - 1;
            });
        }
        if (incBtn) {
            incBtn.addEventListener('click', () => {
                const current = parseInt(input.value || '1', 10);
                if (current < maxStock) {
                    input.value = current + 1;
                } else {
                    window.ShopEase.showToast(`Maximum available stock is ${maxStock}.`, 'warning');
                }
            });
        }
    });
});
