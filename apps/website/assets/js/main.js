(() => {
  const root = document.documentElement;
  const saved = localStorage.getItem('mumtaz-theme');
  if (saved) root.setAttribute('data-theme', saved);

  document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      localStorage.setItem('mumtaz-theme', next);
    });
  });

  const toggle = document.querySelector('[data-nav-toggle]');
  const menu = document.querySelector('[data-nav-menu]');
  if (toggle && menu) {
    toggle.addEventListener('click', () => menu.classList.toggle('open'));
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) { entry.target.classList.add('in-view'); entry.target.classList.add('show'); }
    });
  }, { threshold: 0.16 });

  document.querySelectorAll('.reveal, .reveal-slow, .reveal-fast, .slide-in-left, .slide-in-right, .scale-in, .observe').forEach((el) => observer.observe(el));

  const form = document.querySelector('[data-contact-form]');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = form.querySelector('input[type="email"]');
      if (!email?.value.includes('@')) {
        alert('Please enter a valid email.');
        return;
      }
      alert('Thanks! Our team will contact you shortly.');
      form.reset();
    });
  }
})();
