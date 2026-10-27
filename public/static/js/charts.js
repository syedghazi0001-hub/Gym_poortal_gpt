/**
 * Vanguard Gym OS - Lightweight SVG Chart Renderer
 * Zero CDN dependencies, instant rendering, high-DPI crisp visuals.
 */

function renderAttendanceTrendChart(containerId, data) {
  const container = document.getElementById(containerId);
  if (!container || !data || data.length === 0) return;

  const width = container.clientWidth || 500;
  const height = 220;
  const padding = { top: 20, right: 20, bottom: 40, left: 35 };

  const maxVal = Math.max(...data.map(d => d.count), 5);
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const barW = Math.max(8, (chartW / data.length) - 8);

  let barsSvg = "";
  data.forEach((d, i) => {
    const x = padding.left + i * (chartW / data.length) + (chartW / data.length - barW) / 2;
    const barH = (d.count / maxVal) * chartH;
    const y = padding.top + chartH - barH;

    barsSvg += `
      <g class="chart-bar-group" tabIndex="0">
        <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="4" fill="#10B981" opacity="0.85" />
        <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="4" fill="none" stroke="#34D399" stroke-width="1" opacity="0.4" />
        <text x="${x + barW/2}" y="${height - 12}" fill="#9CA3AF" font-size="10" text-anchor="middle">${d.date}</text>
        <title>${d.full_date}: ${d.count} check-ins</title>
      </g>
    `;
  });

  const svg = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" style="overflow:visible; font-family:sans-serif;">
      <!-- Grid lines -->
      <line x1="${padding.left}" y1="${padding.top}" x2="${width - padding.right}" y2="${padding.top}" stroke="rgba(255,255,255,0.06)" />
      <line x1="${padding.left}" y1="${padding.top + chartH/2}" x2="${width - padding.right}" y2="${padding.top + chartH/2}" stroke="rgba(255,255,255,0.06)" />
      <line x1="${padding.left}" y1="${padding.top + chartH}" x2="${width - padding.right}" y2="${padding.top + chartH}" stroke="rgba(255,255,255,0.12)" />
      
      <!-- Axis numbers -->
      <text x="${padding.left - 8}" y="${padding.top + 4}" fill="#6B7280" font-size="10" text-anchor="end">${maxVal}</text>
      <text x="${padding.left - 8}" y="${padding.top + chartH/2 + 4}" fill="#6B7280" font-size="10" text-anchor="end">${Math.round(maxVal/2)}</text>
      <text x="${padding.left - 8}" y="${padding.top + chartH + 4}" fill="#6B7280" font-size="10" text-anchor="end">0</text>

      ${barsSvg}
    </svg>
  `;

  container.innerHTML = svg;
}

function renderRevenueTrendChart(containerId, data, currency = "PKR") {
  const container = document.getElementById(containerId);
  if (!container || !data || data.length === 0) return;

  const width = container.clientWidth || 500;
  const height = 220;
  const padding = { top: 20, right: 20, bottom: 40, left: 60 };

  const maxVal = Math.max(...data.map(d => d.amount), 10000);
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const barW = Math.max(16, (chartW / data.length) - 16);

  let barsSvg = "";
  data.forEach((d, i) => {
    const x = padding.left + i * (chartW / data.length) + (chartW / data.length - barW) / 2;
    const barH = (d.amount / maxVal) * chartH;
    const y = padding.top + chartH - barH;

    barsSvg += `
      <g class="chart-bar-group" tabIndex="0">
        <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="5" fill="#3B82F6" opacity="0.8" />
        <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="5" fill="none" stroke="#60A5FA" stroke-width="1" opacity="0.5" />
        <text x="${x + barW/2}" y="${height - 12}" fill="#9CA3AF" font-size="11" text-anchor="middle">${d.label}</text>
        <title>${d.label}: ${currency} ${d.amount.toLocaleString()}</title>
      </g>
    `;
  });

  const svg = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" style="overflow:visible; font-family:sans-serif;">
      <!-- Grid lines -->
      <line x1="${padding.left}" y1="${padding.top}" x2="${width - padding.right}" y2="${padding.top}" stroke="rgba(255,255,255,0.06)" />
      <line x1="${padding.left}" y1="${padding.top + chartH/2}" x2="${width - padding.right}" y2="${padding.top + chartH/2}" stroke="rgba(255,255,255,0.06)" />
      <line x1="${padding.left}" y1="${padding.top + chartH}" x2="${width - padding.right}" y2="${padding.top + chartH}" stroke="rgba(255,255,255,0.12)" />

      <!-- Axis numbers -->
      <text x="${padding.left - 8}" y="${padding.top + 4}" fill="#6B7280" font-size="10" text-anchor="end">${(maxVal/1000).toFixed(0)}k</text>
      <text x="${padding.left - 8}" y="${padding.top + chartH/2 + 4}" fill="#6B7280" font-size="10" text-anchor="end">${(maxVal/2000).toFixed(0)}k</text>
      <text x="${padding.left - 8}" y="${padding.top + chartH + 4}" fill="#6B7280" font-size="10" text-anchor="end">0</text>

      ${barsSvg}
    </svg>
  `;

  container.innerHTML = svg;
}
