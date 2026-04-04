/* Mumtaz App Portal — app.js */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {

        var sidebar  = document.getElementById('mzaSidebar');
        var toggle   = document.getElementById('mzaSidebarToggle');
        var overlay  = document.getElementById('mzaSidebarOverlay');

        function openSidebar() {
            if (!sidebar) return;
            sidebar.classList.add('open');
            if (overlay) overlay.classList.add('visible');
            if (toggle) toggle.textContent = '✕';
        }

        function closeSidebar() {
            if (!sidebar) return;
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('visible');
            if (toggle) toggle.textContent = '☰';
        }

        if (toggle) {
            toggle.addEventListener('click', function () {
                if (sidebar && sidebar.classList.contains('open')) {
                    closeSidebar();
                } else {
                    openSidebar();
                }
            });
        }

        if (overlay) {
            overlay.addEventListener('click', closeSidebar);
        }

        // Close sidebar on Escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeSidebar();
        });

        // Close sidebar when a nav link is clicked on mobile
        if (sidebar) {
            var navLinks = sidebar.querySelectorAll('.mza-nav-item[href]');
            navLinks.forEach(function (link) {
                link.addEventListener('click', function () {
                    if (window.innerWidth <= 900) closeSidebar();
                });
            });
        }

    });
})();
