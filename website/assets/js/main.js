(function () {
  'use strict';

  /* --- Mobile nav toggle --- */
  const nav = document.querySelector('[data-nav]');
  const toggle = document.querySelector('[data-nav-toggle]');
  if (nav && toggle) {
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
      const expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
    });
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target) && !toggle.contains(e.target)) {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* --- Copyright year --- */
  document.querySelectorAll('[data-year]').forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });

  /* --- Scroll reveal --- */
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.reveal').forEach(function (el) {
      observer.observe(el);
    });
  } else {
    document.querySelectorAll('.reveal').forEach(function (el) {
      el.classList.add('visible');
    });
  }

  /* --- Billing toggle (pricing page) --- */
  var billingToggle = document.getElementById('billing-toggle');
  if (billingToggle) {
    var isAnnual = true;
    billingToggle.addEventListener('click', function () {
      isAnnual = !isAnnual;
      billingToggle.classList.toggle('active', isAnnual);
      billingToggle.setAttribute('aria-checked', String(isAnnual));

      document.querySelectorAll('.annual-price').forEach(function (el) {
        el.style.display = isAnnual ? '' : 'none';
      });
      document.querySelectorAll('.monthly-price').forEach(function (el) {
        el.style.display = isAnnual ? 'none' : '';
      });
      document.querySelectorAll('.billing-period').forEach(function (el) {
        el.textContent = isAnnual ? 'billed annually' : 'billed monthly';
      });
    });
  }

  /* --- Smooth anchor scroll --- */
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

})();
