/* Mumtaz marketing site — light interactions */
(function () {
  'use strict';

  // Mobile nav toggle
  var burger = document.getElementById('burger');
  var nav = document.getElementById('nav');
  if (burger && nav) {
    burger.addEventListener('click', function () {
      nav.classList.toggle('open');
    });
    // close the menu after tapping a link
    nav.querySelectorAll('.links a').forEach(function (a) {
      a.addEventListener('click', function () { nav.classList.remove('open'); });
    });
  }

  // Current year in the footer
  var y = document.getElementById('year');
  if (y) { y.textContent = new Date().getFullYear(); }

  // Subtle reveal-on-scroll — progressive enhancement only.
  // Content is visible by default (see CSS); we only ADD a gentle entrance
  // when the browser supports it, so JS can never hide content.
  if ('IntersectionObserver' in window) {
    var cards = document.querySelectorAll('.prod, .seg, .step, .feat');
    cards.forEach(function (el) { el.classList.add('reveal'); });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    cards.forEach(function (el) { io.observe(el); });
  }
})();
