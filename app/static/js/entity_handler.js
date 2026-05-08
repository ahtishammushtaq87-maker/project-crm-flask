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

        // History Section
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
                footerHtml += `<a href="${action.url}" class="btn ${action.btn_class} btn-premium me-2">${action.label}</a>`;
            }
        });
        footerHtml += '<button type="button" class="btn btn-secondary btn-premium" data-bs-dismiss="modal">Close</button>';
        modalFooter.innerHTML = footerHtml;
    }
});
