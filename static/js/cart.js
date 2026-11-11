/**
 * ShopEase - Interactive Shopping Cart Controller (AJAX + Live Totals)
 */

document.addEventListener('DOMContentLoaded', () => {
    const updateNavbarBadges = (count) => {
        document.querySelectorAll('[data-cart-badge]').forEach((badge) => {
            badge.textContent = count;
            badge.style.transform = 'scale(1.25)';
            setTimeout(() => {
                badge.style.transform = 'scale(1)';
            }, 200);
        });
    };

    const formatCurrency = (val) => `$${Number(val).toFixed(2)}`;

    // 1. Add to Cart buttons & forms (.js-add-to-cart-form)
    document.querySelectorAll('.js-add-to-cart-form').forEach((form) => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalHTML = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Adding...';
            }

            const formData = new FormData(form);
            const payload = {
                product_id: formData.get('product_id'),
                quantity: formData.get('quantity') || 1
            };

            try {
                const res = await fetch('/cart/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    updateNavbarBadges(data.cart_count);
                    window.ShopEase.showToast(data.message, 'success');
                } else {
                    window.ShopEase.showToast(data.message || 'Could not add item.', 'error');
                }
            } catch (err) {
                form.submit(); // Fallback to standard POST
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalHTML;
                }
            }
        });
    });

    // 2. Cart Page Quantity Update (+/-)
    const syncSummaryTotals = (data) => {
        const subEl = document.getElementById('cart-subtotal');
        const savEl = document.getElementById('cart-savings');
        const shipEl = document.getElementById('cart-shipping');
        const totEl = document.getElementById('cart-total');

        if (subEl) subEl.textContent = formatCurrency(data.subtotal);
        if (savEl) savEl.textContent = `-${formatCurrency(data.discount_savings || 0)}`;
        if (shipEl) shipEl.textContent = data.shipping_fee === 0 ? 'FREE' : formatCurrency(data.shipping_fee);
        if (totEl) totEl.textContent = formatCurrency(data.total_amount);
        updateNavbarBadges(data.cart_count);

        if (data.cart_count === 0) {
            window.location.reload();
        }
    };

    document.querySelectorAll('.js-cart-item').forEach((row) => {
        const productId = row.getAttribute('data-product-id');
        const qtyInput = row.querySelector('.js-cart-qty');
        const lineTotalEl = row.querySelector('.js-line-total');
        const decBtn = row.querySelector('.js-cart-dec');
        const incBtn = row.querySelector('.js-cart-inc');
        const removeBtn = row.querySelector('.js-cart-remove');

        const sendQtyUpdate = async (newQty) => {
            try {
                const res = await fetch('/cart/update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ product_id: productId, quantity: newQty })
                });
                const data = await res.json();
                if (data.success) {
                    if (data.removed) {
                        row.remove();
                        window.ShopEase.showToast(data.message, 'info');
                    } else {
                        if (qtyInput) qtyInput.value = data.quantity;
                        if (lineTotalEl) lineTotalEl.textContent = formatCurrency(data.line_total);
                        window.ShopEase.showToast(data.message, 'info');
                    }
                    syncSummaryTotals(data);
                }
            } catch (err) {
                window.location.reload();
            }
        };

        if (decBtn && qtyInput) {
            decBtn.addEventListener('click', () => {
                const current = parseInt(qtyInput.value || '1', 10);
                if (current <= 1) {
                    window.ShopEase.confirmAction(
                        'Remove Item',
                        'Remove this product from your shopping cart?',
                        () => sendQtyUpdate(0)
                    );
                } else {
                    sendQtyUpdate(current - 1);
                }
            });
        }

        if (incBtn && qtyInput) {
            incBtn.addEventListener('click', () => {
                const current = parseInt(qtyInput.value || '1', 10);
                sendQtyUpdate(current + 1);
            });
        }

        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                window.ShopEase.confirmAction(
                    'Remove Product',
                    'Are you sure you want to remove this product from your cart?',
                    async () => {
                        try {
                            const res = await fetch('/cart/remove', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-Requested-With': 'XMLHttpRequest'
                                },
                                body: JSON.stringify({ product_id: productId })
                            });
                            const data = await res.json();
                            if (data.success) {
                                row.remove();
                                window.ShopEase.showToast(data.message, 'info');
                                syncSummaryTotals(data);
                            }
                        } catch (err) {
                            window.location.reload();
                        }
                    }
                );
            });
        }
    });
});
