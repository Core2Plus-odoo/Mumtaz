/**
 * Oddity Trend — minimal vanilla JS. No dependencies, no build step.
 */
(function () {
	'use strict';

	var toggle = document.querySelector('.menu-toggle');
	var nav = document.getElementById('primary-menu');

	if (!toggle || !nav) {
		return;
	}

	toggle.addEventListener('click', function () {
		var isOpen = nav.classList.toggle('is-open');
		toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
	});
})();
