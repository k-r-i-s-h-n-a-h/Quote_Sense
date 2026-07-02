/**
 * Tatva PM quote form — market rate panel embed.
 *
 * Usage on withtatva.ai/quote (add beside each work item card):
 *
 * <div id="market-rate-slot-0"></div>
 * <script src="https://YOUR_QUOTESENSE_HOST/market-rate-embed.js"></script>
 * <script>
 *   TatvaMarketRate.mount({
 *     slotId: 'market-rate-slot-0',
 *     apiBase: 'https://YOUR_BACKEND/api/market-rate',
 *     serviceType: 'ESSENTIAL',
 *     getFields: () => ({
 *       service_category: document.querySelector('[name=mainService]')?.value,
 *       sub_service: document.querySelector('[name=subService]')?.value,
 *       pricing_method: document.querySelector('[name=pricingMethod]')?.value,
 *       entered_rate: parseFloat(document.querySelector('[name=rate]')?.value || '0'),
 *     }),
 *   });
 * </script>
 */
(function () {
  const VERDICT_CLASS = {
    low: { border: "#fcd34d", bg: "#fffbeb", text: "#92400e", badge: "#fef3c7" },
    high: { border: "#fca5a5", bg: "#fef2f2", text: "#991b1b", badge: "#fee2e2" },
    fair: { border: "#6ee7b7", bg: "#ecfdf5", text: "#065f46", badge: "#d1fae5" },
  };

  function styles(verdict) {
    return VERDICT_CLASS[verdict] || {
      border: "#e2e8f0",
      bg: "#f8fafc",
      text: "#334155",
      badge: "#f1f5f9",
    };
  }

  function render(slot, data, pricingMethod) {
    if (!data || !data.recommend || !data.market_rate) {
      slot.innerHTML = "";
      return;
    }
    const s = styles(data.verdict);
    const unit = data.pricing_method || pricingMethod || "unit";
    slot.innerHTML =
      '<div style="border:1px solid ' +
      s.border +
      ";background:" +
      s.bg +
      ";border-radius:12px;padding:16px;font-family:system-ui,sans-serif;max-width:320px\">" +
      '<div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em">Market guidance</div>' +
      '<div style="font-size:20px;font-weight:700;color:' +
      s.text +
      ';margin-top:6px">~₹' +
      Number(data.market_rate).toLocaleString("en-IN") +
      '<span style="font-size:13px;font-weight:400;color:#64748b"> / ' +
      unit +
      "</span></div>" +
      '<div style="font-size:12px;color:#64748b;margin-top:4px">Based on ' +
      data.weight +
      " vendor quote" +
      (data.weight === 1 ? "" : "s") +
      "</div>" +
      (data.message
        ? '<div style="font-size:13px;color:' +
          s.text +
          ";margin-top:10px;line-height:1.45\">" +
          data.message +
          "</div>"
        : "") +
      "</div>";
  }

  async function fetchRate(apiBase, fields) {
    const hasRate = fields.entered_rate > 0;
    const url = hasRate ? apiBase + "/recommend" : apiBase + "/lookup";
    const opts = hasRate
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            service_type: fields.service_type || "ESSENTIAL",
            service_category: fields.service_category,
            sub_service: fields.sub_service,
            pricing_method: fields.pricing_method,
            entered_rate: fields.entered_rate,
          }),
        }
      : undefined;
    const qs =
      !hasRate &&
      "?" +
        new URLSearchParams({
          service_type: fields.service_type || "ESSENTIAL",
          service_category: fields.service_category,
          sub_service: fields.sub_service,
          pricing_method: fields.pricing_method,
        });
    const res = await fetch(hasRate ? url : url + qs, opts);
    if (!res.ok) return null;
    return res.json();
  }

  function mount(config) {
    const slot = document.getElementById(config.slotId);
    if (!slot) return;
    const apiBase = (config.apiBase || "").replace(/\/$/, "");
    const pollMs = config.pollMs || 800;

    async function refresh() {
      const fields = config.getFields();
      if (
        !fields.service_category ||
        !fields.sub_service ||
        !fields.pricing_method ||
        fields.pricing_method === "Select pricing method"
      ) {
        slot.innerHTML = "";
        return;
      }
      fields.service_type = config.serviceType || fields.service_type || "ESSENTIAL";
      try {
        const data = await fetchRate(apiBase, fields);
        render(slot, data, fields.pricing_method);
      } catch {
        slot.innerHTML = "";
      }
    }

    refresh();
    setInterval(refresh, pollMs);
    if (config.onMount) config.onMount(refresh);
  }

  window.TatvaMarketRate = { mount, fetchRate, render };
})();
