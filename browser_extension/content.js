// Content script - injects AI detection banner on AI sites

(function() {
  const AI_DOMAINS = [
    "chatgpt.com", "openai.com", "claude.ai", "anthropic.com",
    "gemini.google.com", "perplexity.ai", "copilot.microsoft.com",
    "poe.com", "character.ai", "deepseek.com", "mistral.ai",
    "grok.com", "bard.google.com", "aistudio.google.com"
  ];

  const url = window.location.hostname.replace("www.", "");
  if (!AI_DOMAINS.includes(url)) return;

  // Only inject once
  if (window._duAI_injected) return;
  window._duAI_injected = true;

  // Create notification banner
  const banner = document.createElement("div");
  banner.id = "duai-ai-trace-banner";
  banner.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: #1A1A1A;
    border-bottom: 2px solid #EF4444;
    color: #FFFFFF;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    z-index: 2147483647;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    font-size: 13px;
  `;

  banner.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-size: 18px;">🛡️</span>
      <strong>duAI</strong> - AI trace detected on this site
    </div>
    <div style="display: flex; gap: 8px;">
      <button id="duai-clean-trace" style="
        background: #EF4444;
        color: #FFFFFF;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 12px;
        cursor: pointer;
        font-weight: 600;
      ">Limpiar trazas</button>
      <button id="duai-dismiss" style="
        background: transparent;
        color: #888888;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 12px;
        cursor: pointer;
      ">Descartar</button>
    </div>
  `;

  document.body.insertBefore(banner, document.body.firstChild);

  // Clean traces
  document.getElementById("duai-clean-trace").addEventListener("click", () => {
    // Clear site data
    if (navigator.storage && navigator.storage.estimate) {
      navigator.storage.estimate().then(estimate => {
        console.log("duAI: Storage estimate:", estimate);
      });
    }

    // Clear cookies for this domain
    chrome.runtime.sendMessage({ action: "clearBrowserData" }, (response) => {
      if (response && response.success) {
        banner.querySelector("#duai-clean-trace").textContent = "¡Limpiado!";
        banner.querySelector("#duai-clean-trace").style.background = "#10B981";
        setTimeout(() => banner.remove(), 1500);
      }
    });
  });

  // Dismiss
  document.getElementById("duai-dismiss").addEventListener("click", () => {
    banner.remove();
  });

  // Store that user visited an AI site
  chrome.runtime.sendMessage({ action: "aiSiteDetected", domain: url });
})();