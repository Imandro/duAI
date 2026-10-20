// Background service worker for duAI Browser Extension

// AI domains to monitor
const AI_DOMAINS = [
  "chatgpt.com", "openai.com", "claude.ai", "anthropic.com",
  "gemini.google.com", "perplexity.ai", "copilot.microsoft.com",
  "poe.com", "character.ai", "deepseek.com", "mistral.ai",
  "grok.com", "bard.google.com", "aistudio.google.com"
];

// Store AI visit counts
let aiVisitStats = {
  total: 0,
  byDomain: {},
  lastVisit: null,
  sessionVisits: []
};

// Load stats from storage on startup
chrome.storage.local.get(["aiVisitStats"], (result) => {
  if (result.aiVisitStats) {
    aiVisitStats = result.aiVisitStats;
  }
});

// Listen for tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url) {
    const url = new URL(tab.url);
    const domain = url.hostname.replace("www.", "");

    if (AI_DOMAINS.includes(domain)) {
      aiVisitStats.total++;
      aiVisitStats.byDomain[domain] = (aiVisitStats.byDomain[domain] || 0) + 1;
      aiVisitStats.lastVisit = new Date().toISOString();
      aiVisitStats.sessionVisits.push({
        domain,
        url: tab.url,
        timestamp: new Date().toISOString(),
        tabId,
      });

      // Keep only last 100 session visits
      if (aiVisitStats.sessionVisits.length > 100) {
        aiVisitStats.sessionVisits = aiVisitStats.sessionVisits.slice(-100);
      }

      // Save to storage
      chrome.storage.local.set({ aiVisitStats });

      // Show notification badge
      chrome.action.setBadgeText({ text: String(aiVisitStats.total % 1000), tabId });
      chrome.action.setBadgeBackgroundColor({ color: "#EF4444", tabId });
    }
  }
});

// Clear badge when navigating away
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.action.setBadgeText({ text: "", tabId });
});

// Handle messages from content script / popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getStats") {
    sendResponse({ stats: aiVisitStats });
  } else if (request.action === "clearStats") {
    aiVisitStats = { total: 0, byDomain: {}, lastVisit: null, sessionVisits: [] };
    chrome.storage.local.set({ aiVisitStats });
    chrome.action.setBadgeText({ text: "" });
    sendResponse({ success: true });
  } else if (request.action === "clearBrowserData") {
    // Clear browsing data for AI domains
    chrome.browsingData.remove({
      "since": 0
    }, {
      "cookies": true,
      "cache": true,
      "history": true,
      "localStorage": true,
      "downloads": true
    }, (result) => {
      sendResponse({ success: true, result });
    });
    return true; // async response
  }
  return false;
});

// Alarm to periodically clean old data
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "cleanOldStats") {
    // Clean sessions older than 7 days
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    aiVisitStats.sessionVisits = aiVisitStats.sessionVisits.filter(
      v => v.timestamp > weekAgo
    );
    chrome.storage.local.set({ aiVisitStats });
  }
});

// Set up periodic alarm
chrome.alarms.create("cleanOldStats", { periodInMinutes: 60 * 24 }); // Daily