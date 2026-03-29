// Common JavaScript functions

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Show loading spinner
function showLoading() {
    const spinner = `
        <div class="spinner-overlay">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    $('body').append(spinner);
}

// Hide loading spinner
function hideLoading() {
    $('.spinner-overlay').remove();
}

// Confirm action
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Auto-hide alerts
$(document).ready(function() {
    setTimeout(function() {
        $('.alert').fadeOut('slow', function() {
            $(this).remove();
        });
    }, 5000);
});

// Form validation
function validateForm(formId) {
    let isValid = true;
    $(`#${formId} input[required], #${formId} select[required]`).each(function() {
        if (!$(this).val()) {
            $(this).addClass('is-invalid');
            isValid = false;
        } else {
            $(this).removeClass('is-invalid');
        }
    });
    return isValid;
}

// Search functionality
function searchTable(tableId, searchTerm) {
    $(`#${tableId} tbody tr`).each(function() {
        const text = $(this).text().toLowerCase();
        $(this).toggle(text.includes(searchTerm.toLowerCase()));
    });
}