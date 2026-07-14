(() => {
  document.documentElement.classList.add('js-ready');

  const revealElements = document.querySelectorAll('.reveal');

  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -7% 0px', threshold: 0.06 });

    revealElements.forEach((element) => revealObserver.observe(element));
  } else {
    revealElements.forEach((element) => element.classList.add('is-visible'));
  }

  const header = document.querySelector('[data-header]');
  const menuButton = document.querySelector('.menu-button');
  const navLinks = document.querySelectorAll('.site-nav a');

  const setHeaderState = () => {
    header?.classList.toggle('is-scrolled', window.scrollY > 24);
  };

  const setMenuState = (isOpen) => {
    if (!header || !menuButton) return;
    header.classList.toggle('menu-open', isOpen);
    document.body.classList.toggle('menu-open', isOpen);
    menuButton.setAttribute('aria-expanded', String(isOpen));
  };

  setHeaderState();
  window.addEventListener('scroll', setHeaderState, { passive: true });

  menuButton?.addEventListener('click', () => {
    setMenuState(menuButton.getAttribute('aria-expanded') !== 'true');
  });

  navLinks.forEach((link) => link.addEventListener('click', () => setMenuState(false)));

  window.addEventListener('resize', () => {
    if (window.innerWidth > 820) setMenuState(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menuButton?.getAttribute('aria-expanded') === 'true') {
      setMenuState(false);
      menuButton.focus();
    }
  });

  document.querySelectorAll('[data-tab-group]').forEach((group) => {
    const tabList = group.querySelector(':scope > [role="tablist"]');
    const tabs = tabList ? Array.from(tabList.querySelectorAll('[role="tab"]')) : [];
    const panels = tabs
      .map((tab) => document.getElementById(tab.getAttribute('aria-controls')))
      .filter(Boolean);

    const activateTab = (tab, moveFocus = false) => {
      const targetId = tab.getAttribute('aria-controls');

      tabs.forEach((candidate) => {
        const isActive = candidate === tab;
        candidate.setAttribute('aria-selected', String(isActive));
        candidate.setAttribute('tabindex', isActive ? '0' : '-1');
      });

      panels.forEach((panel) => {
        panel.hidden = panel.id !== targetId;
      });

      if (moveFocus) tab.focus();
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activateTab(tab));
      tab.addEventListener('keydown', (event) => {
        let nextIndex = null;

        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          nextIndex = (index + 1) % tabs.length;
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          nextIndex = (index - 1 + tabs.length) % tabs.length;
        } else if (event.key === 'Home') {
          nextIndex = 0;
        } else if (event.key === 'End') {
          nextIndex = tabs.length - 1;
        }

        if (nextIndex === null) return;
        event.preventDefault();
        activateTab(tabs[nextIndex], true);
      });
    });
  });

  const lightbox = document.querySelector('.lightbox');
  const lightboxImage = lightbox?.querySelector('.lightbox-stage img');
  const lightboxCaption = lightbox?.querySelector('[data-lightbox-caption]');
  const lightboxClose = lightbox?.querySelector('.lightbox-close');
  const lightboxFit = lightbox?.querySelector('[data-lightbox-fit]');
  const lightboxActual = lightbox?.querySelector('[data-lightbox-actual]');
  const lightboxStage = lightbox?.querySelector('.lightbox-stage');
  let lastLightboxTrigger = null;

  const setLightboxMode = (showActualSize) => {
    if (!lightbox) return;
    lightbox.classList.toggle('is-actual', showActualSize);
    lightboxFit?.setAttribute('aria-pressed', String(!showActualSize));
    lightboxActual?.setAttribute('aria-pressed', String(showActualSize));
    if (lightboxStage) {
      lightboxStage.scrollTop = 0;
      lightboxStage.scrollLeft = 0;
    }
  };

  const closeLightbox = () => {
    if (!lightbox) return;
    if (typeof lightbox.close === 'function') {
      lightbox.close();
    } else {
      lightbox.removeAttribute('open');
    }
    document.body.classList.remove('lightbox-open');
    lastLightboxTrigger?.focus();
  };

  document.querySelectorAll('[data-lightbox-src]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      if (!lightbox || !lightboxImage) return;
      lastLightboxTrigger = trigger;
      setLightboxMode(false);
      lightboxImage.src = trigger.dataset.lightboxSrc;
      lightboxImage.alt = trigger.dataset.lightboxAlt || '';
      if (lightboxCaption) lightboxCaption.textContent = trigger.dataset.lightboxCaption || '';

      if (typeof lightbox.showModal === 'function') {
        lightbox.showModal();
      } else {
        lightbox.setAttribute('open', '');
      }
      document.body.classList.add('lightbox-open');
      lightboxClose?.focus();
    });
  });

  lightboxClose?.addEventListener('click', closeLightbox);
  lightboxFit?.addEventListener('click', () => setLightboxMode(false));
  lightboxActual?.addEventListener('click', () => setLightboxMode(true));
  lightbox?.addEventListener('click', (event) => {
    if (event.target === lightbox) closeLightbox();
  });
  lightbox?.addEventListener('close', () => {
    document.body.classList.remove('lightbox-open');
    if (lightboxImage) lightboxImage.src = '';
  });

  const copyButton = document.querySelector('[data-copy-citation]');
  const citationText = document.getElementById('citation-text');

  const copyText = async (text) => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  };

  copyButton?.addEventListener('click', async () => {
    if (!citationText) return;
    const label = copyButton.querySelector('span');
    const originalLabel = label?.textContent || 'Copy BibTeX';

    try {
      await copyText(citationText.textContent.trim());
      if (label) label.textContent = 'Copied';
    } catch (error) {
      if (label) label.textContent = 'Copy failed';
    }

    window.setTimeout(() => {
      if (label) label.textContent = originalLabel;
    }, 1800);
  });

  const year = document.querySelector('[data-year]');
  if (year) year.textContent = String(new Date().getFullYear());
})();
