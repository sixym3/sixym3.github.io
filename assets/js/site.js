(function () {
  'use strict';

  var CF_BEACON_TOKEN = '0397e44e7eb54d01919cbb52d0d063e0';          
  if (!CF_BEACON_TOKEN) return;

  var s = document.createElement('script');
  s.defer = true;
  s.src = 'https://static.cloudflareinsights.com/beacon.min.js';
  s.setAttribute('data-cf-beacon', JSON.stringify({ token: CF_BEACON_TOKEN }));
  document.head.appendChild(s);
})();

(function () {
  'use strict';

  var KEY = 'theme';

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function systemDark() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  function current() {
    return document.documentElement.getAttribute('data-theme') || (systemDark() ? 'dark' : 'light');
  }

  function label(btn) {
    var next = current() === 'dark' ? 'light' : 'dark';
    btn.setAttribute('aria-label', 'Switch to ' + next + ' mode');
    btn.setAttribute('title', 'Switch to ' + next + ' mode');
  }

  function init() {
    var btn = document.querySelector('.theme-toggle');
    if (!btn) return;
    label(btn);

    btn.addEventListener('click', function () {
      var next = current() === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      label(btn);
    });

    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function () { if (!stored()) label(btn); };
      mq.addEventListener ? mq.addEventListener('change', onChange) : mq.addListener(onChange);
    }
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
})();


(function () {
  'use strict';

  function els() {
    return {
      box: document.getElementById('lightbox'),
      img: document.getElementById('lightbox-image'),
      vid: document.getElementById('lightbox-video'),
      src: document.getElementById('lightbox-video-source'),
      cap: document.getElementById('lightbox-caption')
    };
  }


  function show(el) { if (el) el.style.display = 'block'; }
  function hide(el) { if (el) el.style.display = 'none'; }

  window.openLightbox = function (img) {
    var e = els();
    if (!e.box) return;
    if (e.vid) e.vid.pause();
    hide(e.vid);
    if (e.img) {
      show(e.img);
      e.img.src = img.currentSrc || img.src;
      e.img.alt = img.alt || '';
    }
    if (e.cap) e.cap.textContent = img.alt || '';
    e.box.classList.add('open');
    document.body.style.overflow = 'hidden';
  };

  window.openVideoLightbox = function (videoSrc, caption) {
    var e = els();
    if (!e.box) return;
    hide(e.img);
    if (e.vid && e.src) {
      show(e.vid);
      e.src.src = videoSrc;
      e.vid.load();
    }
    if (e.cap) e.cap.innerHTML = caption || '';
    e.box.classList.add('open');
    document.body.style.overflow = 'hidden';
  };

  window.closeLightbox = function () {
    var e = els();
    if (!e.box) return;
    if (e.vid) e.vid.pause();
    e.box.classList.remove('open');
    document.body.style.overflow = '';
  };

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') window.closeLightbox();
  });
})();


(function () {
  'use strict';

  function legacyCopy(text) {
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = false;
      try {
        ok = document.execCommand('copy');
      } catch (e) {
        ok = false;
      }
      document.body.removeChild(ta);
      ok ? resolve() : reject(new Error('execCommand copy failed'));
    });
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return legacyCopy(text);
      });
    }
    return legacyCopy(text);
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('.copy-email');
    if (!link) return;

    var email = link.dataset.email;
    if (!email) return;

    e.preventDefault();

    copy(email).then(function () {
      clearTimeout(link._resetTimer);
      link.classList.add('is-copied');
      link._resetTimer = setTimeout(function () {
        link.classList.remove('is-copied');
      }, 1600);
    }).catch(function () {
      window.location.href = link.href;
    });
  });
})();
