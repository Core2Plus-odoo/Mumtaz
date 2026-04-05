/**
 * Mumtaz Website - Advanced Animations
 * Handles scroll triggers, parallax, and interactive elements
 */

class AnimationEngine {
    constructor() {
        this.observedElements = new WeakMap();
        this.init();
    }

    init() {
        this.setupIntersectionObserver();
        this.setupScrollEffects();
        this.setupParallax();
        this.setupMouseEffects();
    }

    setupIntersectionObserver() {
        const options = {
            threshold: [0, 0.1, 0.5, 1],
            rootMargin: '0px 0px -100px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                const element = entry.target;

                if (entry.isIntersecting) {
                    element.classList.add('animate-in');

                    // Stagger children animations
                    const children = element.querySelectorAll('[class*="reveal"]');
                    children.forEach((child, index) => {
                        child.style.animationDelay = `${index * 0.1}s`;
                        child.classList.add('animate-in');
                    });
                }
            });
        }, options);

        // Observe all animated elements
        document.querySelectorAll('[class*="reveal"], [class*="animate"]').forEach((el) => {
            observer.observe(el);
        });
    }

    setupScrollEffects() {
        const scrollElements = document.querySelectorAll('[data-scroll-effect]');

        if (scrollElements.length === 0) return;

        window.addEventListener('scroll', () => {
            scrollElements.forEach((element) => {
                const effect = element.dataset.scrollEffect;
                const progress = this.getScrollProgress(element);

                switch (effect) {
                    case 'fade':
                        element.style.opacity = String(Math.max(0, 1 - progress));
                        break;
                    case 'slide-up':
                        element.style.transform = `translateY(${progress * 50}px)`;
                        break;
                    case 'scale':
                        element.style.transform = `scale(${1 - progress * 0.1})`;
                        break;
                    default:
                        break;
                }
            });
        }, { passive: true });
    }

    setupParallax() {
        const parallaxElements = document.querySelectorAll('[data-parallax]');

        if (parallaxElements.length === 0) return;

        window.addEventListener('scroll', () => {
            parallaxElements.forEach((element) => {
                const speed = Number(element.dataset.parallax || 0.5);
                const yOffset = window.scrollY * speed;
                element.style.transform = `translateY(${yOffset}px)`;
            });
        }, { passive: true });
    }

    setupMouseEffects() {
        const hoverElements = document.querySelectorAll('[data-mouse-follow]');

        if (hoverElements.length === 0) return;

        document.addEventListener('mousemove', (e) => {
            hoverElements.forEach((element) => {
                const rect = element.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const angle = Math.atan2(y - rect.height / 2, x - rect.width / 2) * (180 / Math.PI);

                element.style.setProperty('--mouse-x', `${x}px`);
                element.style.setProperty('--mouse-y', `${y}px`);
                element.style.setProperty('--mouse-angle', `${angle}deg`);
            });
        });
    }

    getScrollProgress(element) {
        const rect = element.getBoundingClientRect();
        const elementTop = rect.top;
        const elementHeight = rect.height;
        const windowHeight = window.innerHeight;

        if (elementTop > windowHeight) return 0;
        if (elementTop + elementHeight < 0) return 1;

        return (windowHeight - elementTop) / (windowHeight + elementHeight);
    }

    // Utility: Create a counter animation
    static createCounter(element, target, duration = 2000) {
        const start = 0;
        const startTime = Date.now();

        const updateCounter = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = Math.floor(start + (target - start) * this.easeOutQuad(progress));

            element.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(updateCounter);
            }
        };

        updateCounter();
    }

    static easeOutQuad(t) {
        return t * (2 - t);
    }

    // Utility: Create wave effect
    static createWaveEffect(element) {
        element.addEventListener('click', (e) => {
            const ripple = document.createElement('span');
            const rect = element.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            ripple.style.width = ripple.style.height = `${size}px`;
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            ripple.classList.add('ripple');

            element.appendChild(ripple);

            setTimeout(() => ripple.remove(), 600);
        });
    }
}

// Initialize animations when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new AnimationEngine();
    });
} else {
    new AnimationEngine();
}
