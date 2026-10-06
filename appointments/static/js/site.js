// randevu_sistemi/appointments/static/js/site.js

// Global variables
let currentUser = null;
let notificationCount = 0;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize components
    initializeNavbar();
    initializeNotifications();
    initializeFormValidation();
    initializeAnimations();
    initializeTooltips();
    initializeCounters();
    
    // Auto-refresh for real-time updates
    if (isUserAuthenticated()) {
        startAutoRefresh();
    }
    
    console.log('BeautyTime App initialized successfully!');
}

// Navbar functionality
function initializeNavbar() {
    const navbar = document.querySelector('.navbar');
    
    // Scroll effect
    window.addEventListener('scroll', function() {
        if (window.scrollY > 100) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
    
    // Mobile menu auto-close
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (navbarCollapse.classList.contains('show')) {
                new bootstrap.Collapse(navbarCollapse).hide();
            }
        });
    });
}

// Notification system
function initializeNotifications() {
    if (isUserAuthenticated()) {
        updateNotificationBadge();
        // Check for new notifications every 30 seconds
        setInterval(updateNotificationBadge, 30000);
    }
}

function updateNotificationBadge() {
    fetch('/api/notifications/count/')
        .then(response => response.json())
        .then(data => {
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                if (data.unread_count > 0) {
                    badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(error => console.log('Notification update failed:', error));
}

// Form validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Focus on first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                    
                    // Show custom error message
                    const errorMsg = firstInvalid.dataset.errorMessage || 'Bu alan zorunludur.';
                    toastr.error(errorMsg);
                }
            } else {
                // Show loading state
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    showLoadingButton(submitBtn);
                }
            }
            
            form.classList.add('was-validated');
        });
        
        // Real-time validation
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });
            
            input.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) {
                    validateField(this);
                }
            });
        });
    });
}

function validateField(field) {
    const isValid = field.checkValidity();
    
    field.classList.remove('is-valid', 'is-invalid');
    field.classList.add(isValid ? 'is-valid' : 'is-invalid');
    
    // Custom validation messages
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback && !isValid) {
        feedback.textContent = field.dataset.errorMessage || field.validationMessage;
    }
}

function showLoadingButton(button) {
    const originalText = button.innerHTML;
    const loadingText = button.dataset.loadingText || 'Yükleniyor...';
    
    button.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${loadingText}`;
    button.disabled = true;
    
    // Reset after 10 seconds (fallback)
    setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
    }, 10000);
}

// Animations
function initializeAnimations() {
    // Parallax effect for hero section
    const heroSection = document.querySelector('.hero-section');
    if (heroSection) {
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const parallax = heroSection.querySelector('.hero-content');
            if (parallax) {
                parallax.style.transform = `translateY(${scrolled * 0.5}px)`;
            }
        });
    }
    
    // Count-up animation for stats
    animateCounters();
    
    // Intersection Observer for fade-in animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe elements with animation class
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

function animateCounters() {
    const counters = document.querySelectorAll('.stats-number');
    
    counters.forEach(counter => {
        const target = parseInt(counter.textContent.replace(/[^0-9]/g, ''));
        const duration = 2000; // 2 seconds
        const step = target / (duration / 16); // 60fps
        let current = 0;
        
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            
            // Format number with + if needed
            const formatted = Math.floor(current);
            if (counter.textContent.includes('+')) {
                counter.textContent = formatted + '+';
            } else {
                counter.textContent = formatted;
            }
        }, 16);
    });
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize counters
function initializeCounters() {
    // Auto-update appointment counters
    if (document.querySelector('.appointment-stats')) {
        updateAppointmentStats();
    }
}

function updateAppointmentStats() {
    fetch('/api/dashboard/stats/')
        .then(response => response.json())
        .then(data => {
            // Update stat cards if they exist
            updateStatCard('total-appointments', data.total_appointments);
            updateStatCard('pending-appointments', data.pending_appointments);
            updateStatCard('confirmed-appointments', data.confirmed_appointments);
            updateStatCard('completed-appointments', data.completed_appointments);
        })
        .catch(error => console.log('Stats update failed:', error));
}

function updateStatCard(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

// Auto-refresh system
function startAutoRefresh() {
    // Refresh every 60 seconds
    setInterval(() => {
        updateNotificationBadge();
        
        // Update appointment status if on appointments page
        if (window.location.pathname.includes('/appointments/')) {
            refreshAppointmentStatus();
        }
    }, 60000);
}

function refreshAppointmentStatus() {
    const appointmentCards = document.querySelectorAll('[data-appointment-id]');
    
    appointmentCards.forEach(card => {
        const appointmentId = card.dataset.appointmentId;
        
        fetch(`/api/appointments/${appointmentId}/status/`)
            .then(response => response.json())
            .then(data => {
                const statusBadge = card.querySelector('.appointment-status');
                if (statusBadge && statusBadge.textContent !== data.status) {
                    statusBadge.textContent = data.status;
                    statusBadge.className = `badge appointment-status ${getStatusClass(data.status)}`;
                    
                    // Show notification
                    toastr.info(`Randevu durumu güncellendi: ${data.status}`);
                }
            })
            .catch(error => console.log('Status refresh failed:', error));
    });
}

function getStatusClass(status) {
    const statusClasses = {
        'Beklemede': 'bg-warning text-dark',
        'Onaylandı': 'bg-success',
        'İptal Edildi': 'bg-danger',
        'Tamamlandı': 'bg-info'
    };
    return statusClasses[status] || 'bg-secondary';
}

// Utility functions
function isUserAuthenticated() {
    // Check if user is logged in (can be enhanced)
    return document.querySelector('[data-user-authenticated]') !== null;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('tr-TR', options);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY'
    }).format(amount);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Search functionality
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        const debouncedSearch = debounce(performSearch, 300);
        searchInput.addEventListener('input', debouncedSearch);
    }
}

function performSearch() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const items = document.querySelectorAll('.searchable-item');
    
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(query)) {
            item.style.display = 'block';
            item.style.opacity = '1';
        } else {
            item.style.display = 'none';
            item.style.opacity = '0';
        }
    });
}

// Calendar integration
function initializeCalendar(calendarEl, events = []) {
    if (!calendarEl) return;
    
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'tr',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,listWeek'
        },
        height: 'auto',
        events: events,
        eventClick: function(info) {
            showAppointmentDetails(info.event);
        },
        dateClick: function(info) {
            if (info.date >= new Date()) {
                window.location.href = `/appointments/create/?date=${info.dateStr}`;
            }
        },
        eventDidMount: function(info) {
            // Add tooltip to events
            info.el.setAttribute('title', info.event.title);
            info.el.setAttribute('data-bs-toggle', 'tooltip');
            new bootstrap.Tooltip(info.el);
        }
    });
    
    calendar.render();
    return calendar;
}

function showAppointmentDetails(event) {
    const appointmentId = event.id;
    
    // Show modal with appointment details
    const modalHtml = `
        <div class="modal fade" id="appointmentDetailModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Randevu Detayları</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>Hizmet:</strong> ${event.title}</p>
                        <p><strong>Tarih:</strong> ${formatDate(event.start)}</p>
                        <p><strong>Durum:</strong> <span class="badge bg-primary">${event.extendedProps.status}</span></p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Kapat</button>
                        <a href="/appointments/${appointmentId}/" class="btn btn-primary">Detayları Gör</a>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('appointmentDetailModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('appointmentDetailModal'));
    modal.show();
}

// Image lazy loading
function initializeLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    
    images.forEach(img => imageObserver.observe(img));
}

// Error handling
window.addEventListener('error', function(e) {
    console.error('JavaScript Error:', e.error);
    // Optionally send error to logging service
});

// Service Worker registration (for PWA features)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('ServiceWorker registration successful');
            })
            .catch(error => {
                console.log('ServiceWorker registration failed');
            });
    });
}

// Export functions for global use
window.BeautyTime = {
    formatDate,
    formatCurrency,
    showLoadingButton,
    updateNotificationBadge,
    initializeCalendar,
    performSearch
};