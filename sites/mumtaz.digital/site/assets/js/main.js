/**
 * Mumtaz Premium Website
 * Main JavaScript Bundle
 */

class MumtazWebsite {
    constructor() {
        this.initNavigation();
        this.initTheme();
        this.initScrollAnimations();
        this.initIntersectionObserver();
        this.initFormValidation();
    }

    // Navigation
    initNavigation() {
        const navToggle = document.querySelector('[data-toggle-nav]') || document.querySelector('[data-nav-toggle]');
        const navMenu = document.querySelector('[data-nav-menu]');
        const navLinks = navMenu ? navMenu.querySelectorAll('.nav-link') : [];

        if (navToggle && navMenu) {
            navToggle.addEventListener('click', () => {
                navMenu.classList.toggle('active');
                navMenu.classList.toggle('open');
                navToggle.setAttribute('aria-expanded', String(navMenu.classList.contains('active') || navMenu.classList.contains('open')));
            });

            navLinks.forEach((link) => {
                link.addEventListener('click', () => {
                    navMenu.classList.remove('active');
                    navMenu.classList.remove('open');
                    navToggle.setAttribute('aria-expanded', 'false');
                });
            });
        }

        // Active link on scroll
        window.addEventListener('scroll', () => {
            this.updateActiveNavLink();
        }, { passive: true });
    }

    updateActiveNavLink() {
        const navLinks = document.querySelectorAll('.nav-link');
        const scrollPos = window.scrollY + 100;

        navLinks.forEach((link) => {
            const sectionId = link.getAttribute('href');
            if (!sectionId || !sectionId.startsWith('#')) {
                return;
            }
            const section = document.querySelector(sectionId);
            if (section && scrollPos >= section.offsetTop && scrollPos < section.offsetTop + section.offsetHeight) {
                navLinks.forEach((navLink) => navLink.classList.remove('active'));
                link.classList.add('active');
            }
        });
    }

    // Theme Toggle
    initTheme() {
        const themeToggle = document.querySelector('[data-theme-toggle]');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const savedTheme = localStorage.getItem('theme') || localStorage.getItem('mumtaz-theme');
        const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');

        this.setTheme(currentTheme);

        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                this.setTheme(newTheme);
                localStorage.setItem('theme', newTheme);
                localStorage.setItem('mumtaz-theme', newTheme);
            });
        }
    }

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (theme === 'dark') {
            document.documentElement.style.colorScheme = 'dark';
        } else {
            document.documentElement.style.colorScheme = 'light';
        }
    }

    // Scroll Animations
    initScrollAnimations() {
        const elements = document.querySelectorAll('[class*="reveal"]');

        elements.forEach((element) => {
            const delay = element.classList.contains('reveal-delay-1') ? 0.2 : 0;
            element.style.animationDelay = `${delay}s`;
        });
    }

    // Intersection Observer for elements
    initIntersectionObserver() {
        document.body.classList.add('js-ready');
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -100px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('in-view');
                    if (!entry.target.classList.contains('observe')) {
                        observer.unobserve(entry.target);
                    }
                }
            });
        }, observerOptions);

        document.querySelectorAll('.observe, .reveal, .reveal-slow, .reveal-fast, .slide-in-left, .slide-in-right, .scale-in').forEach((element) => {
            observer.observe(element);
        });
    }

    // Form Validation
    initFormValidation() {
        const forms = document.querySelectorAll('form');

        forms.forEach((form) => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                }
            });
        });
    }

    validateForm(form) {
        const inputs = form.querySelectorAll('input, textarea, select');
        let isValid = true;

        inputs.forEach((input) => {
            if (!this.validateField(input)) {
                isValid = false;
            }
        });

        return isValid;
    }

    validateField(field) {
        if (!field.value.trim()) {
            field.classList.add('error');
            return false;
        }

        if (field.type === 'email') {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(field.value)) {
                field.classList.add('error');
                return false;
            }
        }

        field.classList.remove('error');
        return true;
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new MumtazWebsite();
    });
} else {
    new MumtazWebsite();
}

// Smooth scroll polyfill
function smoothScroll(target) {
    const element = document.querySelector(target);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

// Utility functions
window.utils = {
    // Format currency
    formatCurrency(amount, currency = 'AED') {
        return new Intl.NumberFormat('en-AE', {
            style: 'currency',
            currency
        }).format(amount);
    },

    // Format percentage
    formatPercentage(value) {
        return `${(value * 100).toFixed(1)}%`;
    },

    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Track event
    trackEvent(category, action, label) {
        if (window.gtag) {
            gtag('event', action, {
                event_category: category,
                event_label: label
            });
        }
    }
};

window.smoothScroll = smoothScroll;

// ── FAQ accordion ──────────────────────────────────────
function toggleFaq(btn) {
  const item = btn.closest('.faq-item');
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.faq-item.open').forEach(el => el.classList.remove('open'));
  if (!isOpen) item.classList.add('open');
}
window.toggleFaq = toggleFaq;

// ── Animated counters ──────────────────────────────────
function animateCounter(el, target, suffix) {
  let start = 0;
  const step = target / 60;
  const timer = setInterval(() => {
    start += step;
    if (start >= target) { start = target; clearInterval(timer); }
    el.textContent = Math.floor(start) + suffix;
  }, 16);
}

const counterObs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (!e.isIntersecting) return;
    const el = e.target;
    const val = el.dataset.count;
    const suffix = el.dataset.suffix || '';
    animateCounter(el, parseFloat(val), suffix);
    counterObs.unobserve(el);
  });
}, { threshold: 0.5 });

document.querySelectorAll('[data-count]').forEach(el => counterObs.observe(el));

/* ── Pricing tab switcher ──────────────────────────────────────── */
document.querySelectorAll('.pricing-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const panel = tab.dataset.tab;
    document.querySelectorAll('.pricing-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('[data-tab-panel]').forEach(p => {
      p.style.display = p.dataset.tabPanel === panel ? 'grid' : 'none';
    });
  });
});
