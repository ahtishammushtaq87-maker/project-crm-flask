/**
 * Entity History Handler
 * Handles global entity history triggers and modal population
 */
document.addEventListener('DOMContentLoaded', function() {
    const modalElement = document.getElementById('entityHistoryModal');
    if (!modalElement) return;

    const modal = new bootstrap.Modal(modalElement);
    const modalTitle = modalElement.querySelector('.modal-title');
    const modalBody = modalElement.querySelector('.modal-body');
    const modalFooter = modalElement.querySelector('.modal-footer');

    // Track current inventory fetch params so history filter reloads can reference them
    let _currentInventoryEntityId = null;

    // Global click handler for better conflict management
    document.addEventListener('click', function(e) {
        const trigger = e.target.closest('.entity-history-trigger');
        if (!trigger) return;
        
        // Explicitly stop propagation to prevent other row/image listeners from firing
        e.stopPropagation();

        const entityType = trigger.dataset.entityType;
        const entityId = trigger.dataset.entityId;

        if (!entityType || !entityId) return;

        // If it doesn't have data-bs-toggle, we trigger it manually
        if (trigger.dataset.bsToggle !== 'modal') {
            e.preventDefault();
            showLoading();
            modal.show();

            if (entityType === 'inventory') {
                _currentInventoryEntityId = entityId;
            }

            fetch(`/api/entity-details/${entityType}/${entityId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        populateModal(data);
                    } else {
                        showError(data.error || 'Failed to load details');
                    }
                })
                .catch(err => {
                    showError('Network error while loading details');
                    console.error(err);
                });
        }
    });

    // Handle data loading when modal is opened via Bootstrap Data API
    modalElement.addEventListener('show.bs.modal', function(event) {
        const trigger = event.relatedTarget;
        if (!trigger || !trigger.classList.contains('entity-history-trigger')) {
            return;
        }

        const entityType = trigger.dataset.entityType;
        const entityId = trigger.dataset.entityId;

        if (!entityType || !entityId) return;

        if (entityType === 'inventory') {
            _currentInventoryEntityId = entityId;
        }

        showLoading();

        fetch(`/api/entity-details/${entityType}/${entityId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    populateModal(data);
                } else {
                    showError(data.error || 'Failed to load details');
                }
            })
            .catch(err => {
                showError('Network error while loading details');
                console.error(err);
            });
    });

    // Called when user changes the history limit dropdown
    window._reloadInventoryHistory = function(limitValue) {
        if (!_currentInventoryEntityId) return;
        showLoading();
        fetch(`/api/entity-details/inventory/${_currentInventoryEntityId}?history_limit=${limitValue}`)
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    populateModal(data);
                } else {
                    showError(data.error || 'Failed to reload history');
                }
            })
            .catch(err => {
                showError('Network error while reloading history');
                console.error(err);
            });
    };

    function showLoading() {
        modalTitle.textContent = 'Loading...';
        modalBody.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Fetching history details...</p>
            </div>
        `;
        modalFooter.innerHTML = '';
    }

    function showError(msg) {
        modalTitle.textContent = 'Error';
        modalBody.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle me-2"></i> ${msg}
            </div>
        `;
        modalFooter.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>';
    }

    function populateModal(data) {
        modalTitle.textContent = data.title;
        
        let html = '';

        // Image if available (Profile size)
        if (data.image) {
            html += `
                <div class="entity-image-wrapper">
                    <div class="entity-image-container">
                        <img src="${data.image}" alt="Reference Image" />
                        <div class="image-overlay">Reference</div>
                    </div>
                </div>
            `;
        }

        // Summary Card
        html += '<div class="entity-summary-card">';
        data.details.forEach(detail => {
            html += `
                <div class="summary-item">
                    <label>${detail.label}</label>
                    <span class="${detail.class || ''}">${detail.value}</span>
                </div>
            `;
        });
        html += '</div>';

        // ---- Manufacturing / 3-column layout for inventory ----
        if (data.has_manufacturing_history) {
            const currentLimit = data.history_limit || '5';
            const totalSale = data.total_sale_count || 0;
            const totalPurchase = data.total_purchase_count || 0;
            const totalMfg = data.total_mfg_count || 0;

            // History Filter Controls
            html += `
                <div class="d-flex align-items-center justify-content-between mb-3 mt-2">
                    <h6 class="mb-0 fw-bold"><i class="fas fa-history me-2"></i> Full History</h6>
                    <div class="d-flex align-items-center gap-2">
                        <span class="text-muted small me-1">Show:</span>
                        ${['5','10','20','all'].map(v => `
                            <button class="btn btn-sm ${currentLimit === v ? 'btn-primary' : 'btn-outline-secondary'} py-0 px-2"
                                onclick="_reloadInventoryHistory('${v}')" style="font-size:0.8rem;">
                                ${v === 'all' ? 'All' : v}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;

            // 3-column row
            html += '<div class="row g-2">';

            // ---- Column 1: Sales ----
            html += '<div class="col-12 col-md-4">';
            html += `<div class="p-2 border rounded h-100">
                <h6 class="text-success mb-2"><i class="fas fa-arrow-up me-1"></i> Sales
                    <span class="badge bg-success ms-1" style="font-size:0.7rem;">${totalSale}</span>
                </h6>`;
            const sales = data.history.filter(i => i.type === 'sale');
            if (sales.length > 0) {
                html += '<div class="history-timeline small">';
                sales.forEach(item => {
                    html += `
                        <div class="timeline-item sale mb-2">
                            <div class="timeline-content">
                                <div class="timeline-date text-muted" style="font-size:0.75rem;">${item.date}</div>
                                <div class="timeline-event">${item.event}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html += '<p class="text-muted small mb-0">No sales history.</p>';
            }
            html += '</div></div>';

            // ---- Column 2: Purchases ----
            html += '<div class="col-12 col-md-4">';
            html += `<div class="p-2 border rounded h-100">
                <h6 class="text-primary mb-2"><i class="fas fa-arrow-down me-1"></i> Purchases
                    <span class="badge bg-primary ms-1" style="font-size:0.7rem;">${totalPurchase}</span>
                </h6>`;
            const purchases = data.history.filter(i => i.type === 'purchase');
            if (purchases.length > 0) {
                html += '<div class="history-timeline small">';
                purchases.forEach(item => {
                    html += `
                        <div class="timeline-item purchase mb-2">
                            <div class="timeline-content">
                                <div class="timeline-date text-muted" style="font-size:0.75rem;">${item.date}</div>
                                <div class="timeline-event">${item.event}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html += '<p class="text-muted small mb-0">No purchases history.</p>';
            }
            html += '</div></div>';

            // ---- Column 3: Manufacturing / Production ----
            html += '<div class="col-12 col-md-4">';
            html += `<div class="p-2 border rounded h-100" style="border-color:#fd7e14 !important;">
                <h6 class="text-warning mb-2"><i class="fas fa-industry me-1"></i> Manufacturing
                    <span class="badge bg-warning text-dark ms-1" style="font-size:0.7rem;">${totalMfg}</span>
                </h6>`;
            const mfgHistory = data.manufacturing_history || [];
            if (mfgHistory.length > 0) {
                html += '<div class="history-timeline small">';
                mfgHistory.forEach(item => {
                    const iconClass = item.type === 'component_used'
                        ? 'fas fa-cogs text-secondary'
                        : 'fas fa-box-open text-success';
                    const badgeLabel = item.type === 'component_used'
                        ? '<span class="badge bg-secondary" style="font-size:0.65rem;">Component Used</span>'
                        : '<span class="badge bg-warning text-dark" style="font-size:0.65rem;">Finished Good</span>';
                    html += `
                        <div class="timeline-item mb-2">
                            <div class="timeline-content">
                                <div class="d-flex align-items-center gap-1 mb-1">
                                    <i class="${iconClass}" style="font-size:0.8rem;"></i>
                                    ${badgeLabel}
                                    <span class="text-muted ms-auto" style="font-size:0.7rem;">${item.date}</span>
                                </div>
                                <div class="timeline-event">${item.event}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html += '<p class="text-muted small mb-0">No manufacturing history.</p>';
            }
            html += '</div></div>';

            html += '</div>'; // end row

        } else if (data.split_history_layout) {
            // Original 2-column layout (sales + purchases)
            html += '<h6 class="mb-3 fw-bold"><i class="fas fa-history me-2"></i> Full History</h6>';
            if (data.history && data.history.length > 0) {
                html += '<div class="row">';
                
                // Sold History Column
                html += '<div class="col-md-6 border-end">';
                html += '<h6 class="text-success"><i class="fas fa-arrow-up me-1"></i> Sold History</h6>';
                const sales = data.history.filter(i => i.type === 'sale');
                if (sales.length > 0) {
                    html += '<div class="history-timeline">';
                    sales.forEach(item => {
                        html += `
                            <div class="timeline-item ${item.type || ''}">
                                <div class="timeline-content">
                                    <div class="timeline-date">${item.date}</div>
                                    <div class="timeline-event">${item.event}</div>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                } else {
                    html += '<p class="text-muted small">No recent sales.</p>';
                }
                html += '</div>';
                
                // Purchase History Column
                html += '<div class="col-md-6">';
                html += '<h6 class="text-primary"><i class="fas fa-arrow-down me-1"></i> Purchase History</h6>';
                const purchases = data.history.filter(i => i.type === 'purchase');
                if (purchases.length > 0) {
                    html += '<div class="history-timeline">';
                    purchases.forEach(item => {
                        html += `
                            <div class="timeline-item ${item.type || ''}">
                                <div class="timeline-content">
                                    <div class="timeline-date">${item.date}</div>
                                    <div class="timeline-event">${item.event}</div>
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                } else {
                    html += '<p class="text-muted small">No recent purchases.</p>';
                }
                html += '</div>';
                
                html += '</div>'; // End row
            } else {
                html += '<p class="text-muted small">No history records found for this entity.</p>';
            }
        } else {
            // Single-column layout
            html += '<h6 class="mb-3 fw-bold"><i class="fas fa-history me-2"></i> Full History</h6>';
            if (data.history && data.history.length > 0) {
                html += '<div class="history-timeline">';
                data.history.forEach(item => {
                    html += `
                        <div class="timeline-item ${item.type || ''}">
                            <div class="timeline-content">
                                <div class="timeline-date">${item.date}</div>
                                <div class="timeline-event">${item.event}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else {
                html += '<p class="text-muted small">No history records found for this entity.</p>';
            }
        }

        modalBody.innerHTML = html;

        // Footer Actions
        let footerHtml = '';
        data.actions.forEach(action => {
            if (action.is_form) {
                footerHtml += `
                    <form action="${action.url}" method="POST" class="d-inline" onsubmit="return confirm('Are you sure you want to perform this action?');">
                        <button type="submit" class="btn ${action.btn_class} btn-premium me-2">${action.label}</button>
                    </form>
                `;
            } else {
                let onclickAttr = action.onclick ? `onclick="${action.onclick}"` : '';
                footerHtml += `<a href="${action.url}" ${onclickAttr} class="btn ${action.btn_class} btn-premium me-2">${action.label}</a>`;
            }
        });
        footerHtml += '<button type="button" class="btn btn-secondary btn-premium" data-bs-dismiss="modal">Close</button>';
        modalFooter.innerHTML = footerHtml;
    }
});
