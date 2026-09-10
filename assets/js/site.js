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
      e.img.src = img.getAttribute('data-full') || img.currentSrc || img.src;
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

/* Video loading policy for the whole site.
   Markup ships preload="none", so a page paints without fetching a single
   video. Whatever is on screen starts playing straight away and loops; once
   the page has finished loading, the off-screen clips are warmed one at a
   time so they are buffered before the reader reaches them.

   load() aborts playback, so anything currently on screen is never warmed —
   play() is already fetching it, and calling load() would reset it to paused.

   Narrow viewports get the -sm encode, roughly a third the bytes. */
(function () {
  'use strict';

  var vids = Array.prototype.slice.call(document.querySelectorAll('video.autoplay-in-view'));
  if (!vids.length) return;

  var mq = window.matchMedia || null;
  var reduced = mq && mq('(prefers-reduced-motion: reduce)').matches;
  var small = mq && mq('(max-width: 700px)').matches;

  var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  var thrifty = !!(conn && (conn.saveData || /^([23]g|slow-2g)$/.test(conn.effectiveType || '')));

  var onScreen = [];
  function visible(v) { return onScreen.indexOf(v) !== -1; }

  if (small) {
    vids.forEach(function (v) {
      var s = v.querySelector('source');
      if (s && s.src && !/-sm\.mp4$/.test(s.src)) {
        s.src = s.src.replace(/\.mp4$/, '-sm.mp4');
        v.load();
      }
    });
  }

  // A play() on an empty buffer can reject; try again once there is data.
  function tryPlay(v) {
    var p = v.play();
    if (!p || !p.catch) return;
    p.catch(function () {
      v.addEventListener('canplay', function once() {
        v.removeEventListener('canplay', once);
        if (!visible(v)) return;
        var q = v.play();
        if (q && q.catch) q.catch(function () {});
      });
    });
  }

  if (reduced) return;

  function mark(v, on) {
    var i = onScreen.indexOf(v);
    if (on) {
      if (i === -1) onScreen.push(v);
      tryPlay(v);
    } else {
      if (i !== -1) onScreen.splice(i, 1);
      if (!v.paused) v.pause();
    }
  }

  // Belt and braces for the observer: if the page reflows after load — late
  // fonts, images filling in, a window resize — a clip can end up on screen
  // without the observer having fired for it. Re-measure and reconcile.
  function reconcile() {
    var h = window.innerHeight || document.documentElement.clientHeight;
    vids.forEach(function (v) {
      var r = v.getBoundingClientRect();
      if (!r.width && !r.height) return;          // not laid out yet
      mark(v, r.top < h + 150 && r.bottom > -150);
    });
  }

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { mark(entry.target, entry.isIntersecting); });
    }, { rootMargin: '150px 0px', threshold: 0 });
    vids.forEach(function (v) { io.observe(v); });
  } else {
    reconcile();
    window.addEventListener('scroll', reconcile, { passive: true });
  }

  var pending;
  function later() { clearTimeout(pending); pending = setTimeout(reconcile, 200); }
  window.addEventListener('resize', later);
  window.addEventListener('pageshow', later);
  window.addEventListener('load', later);

  if (thrifty) return;

  function warm() {
    var queue = vids.filter(function (v) { return v.readyState < 3 && !visible(v); });
    var idle = window.requestIdleCallback || function (fn) { return setTimeout(fn, 200); };

    (function next() {
      var v = queue.shift();
      if (!v) return;
      if (v.readyState >= 3 || visible(v)) return next();

      var done = false;
      var advance = function () {
        if (done) return;
        done = true;
        v.removeEventListener('loadeddata', advance);
        if (visible(v)) tryPlay(v);   // it scrolled in while we were fetching
        idle(next);
      };
      v.addEventListener('loadeddata', advance);
      setTimeout(advance, 4000);      // one stalled file must not block the queue

      v.preload = 'auto';
      v.load();
    })();
  }

  if (document.readyState === 'complete') warm();
  else window.addEventListener('load', function () { setTimeout(warm, 400); });
})();
