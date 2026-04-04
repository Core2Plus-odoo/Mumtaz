/* Mumtaz Website — JS */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {

        // Mobile nav toggle
        var toggle = document.getElementById('mzwMobileToggle');
        var menu   = document.getElementById('mzwMobileMenu');
        if (toggle && menu) {
            toggle.addEventListener('click', function () {
                menu.classList.toggle('open');
                toggle.textContent = menu.classList.contains('open') ? '✕' : '☰';
            });
        }

        // Sticky nav background on scroll
        var nav = document.querySelector('.mzw-nav');
        if (nav) {
            window.addEventListener('scroll', function () {
                if (window.scrollY > 20) {
                    nav.style.background = 'rgba(6,11,20,0.98)';
                } else {
                    nav.style.background = 'rgba(6,11,20,0.92)';
                }
            });
        }

    });
})();
