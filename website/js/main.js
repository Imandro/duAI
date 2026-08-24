document.addEventListener("DOMContentLoaded", () => {
    initLangToggle();
    initScreenshotTabs();
    initScrollFade();
    fetchGitHubStats();
});

function initLangToggle() {
    const btn = document.getElementById("btn-lang");
    if (!btn) return;
    btn.addEventListener("click", () => {
        const current = localStorage.getItem("duai-lang") || "es";
        const next = current === "es" ? "en" : "es";
        setLanguage(next);
    });
}

function initScreenshotTabs() {
    const tabs = document.querySelectorAll(".screenshot-tab");
    const img = document.getElementById("screenshot-img");
    if (!tabs.length || !img) return;

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            const name = tab.dataset.tab;
            img.style.opacity = "0";
            setTimeout(() => {
                img.src = `assets/screenshots/${name}.png`;
                img.alt = `duAI ${name}`;
                img.style.opacity = "1";
            }, 200);
        });
    });

    img.style.transition = "opacity 0.2s ease";
}

function initScrollFade() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add("fade-up");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll(
        ".feature-card, .step, .target-group, .faq-item, .download-card"
    ).forEach(el => {
        el.style.opacity = "0";
        observer.observe(el);
    });
}

function fetchGitHubStats() {
    fetch("https://api.github.com/repos/Imandro/duAI")
        .then(r => r.json())
        .then(data => {
            if (data.message === "Not Found") return;

            const starsEl = document.getElementById("stat-stars");
            const forksEl = document.getElementById("stat-forks");
            const navStarsEl = document.getElementById("gh-stars");

            if (starsEl) starsEl.textContent = formatNumber(data.stargazers_count);
            if (forksEl) forksEl.textContent = formatNumber(data.forks_count);
            if (navStarsEl) navStarsEl.textContent = formatNumber(data.stargazers_count);
        })
        .catch(() => {});
}

function formatNumber(n) {
    if (n >= 1000) return (n / 1000).toFixed(1) + "k";
    return String(n);
}
