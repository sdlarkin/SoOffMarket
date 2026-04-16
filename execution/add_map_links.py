"""
Add Google Maps satellite and Street View links to comped parcel data.
Also generates an HTML viewer for quick visual evaluation of each parcel.

Queries ArcGIS for parcel centroids in WGS84, builds Google URLs,
and outputs an interactive HTML page for buildability review.
"""

import csv
import json
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp" / "sara_holt_segments"

INPUT_CSV = TMP_DIR / "individuals_comped.csv"
OUTPUT_CSV = TMP_DIR / "individuals_final.csv"
OUTPUT_HTML = TMP_DIR / "parcel_viewer.html"

PARCEL_URL = "https://mapsdev.hamiltontn.gov/hcwa03/rest/services/Live_Parcels/MapServer/0/query"


def get_geometries_batch(tax_map_nos: list[str]) -> dict[str, dict]:
    """Get full polygon geometries + centroids in WGS84 for a batch of parcels."""
    ids_str = ",".join(f"'{pid}'" for pid in tax_map_nos)
    r = requests.post(PARCEL_URL, data={
        "where": f"TAX_MAP_NO IN ({ids_str})",
        "outFields": "TAX_MAP_NO",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }, timeout=30)
    data = r.json()
    results = {}
    for feat in data.get("features", []):
        pid = feat["attributes"]["TAX_MAP_NO"]
        rings = feat["geometry"].get("rings", [[]])
        if rings and rings[0]:
            pts = rings[0]
            lat = sum(p[1] for p in pts) / len(pts)
            lon = sum(p[0] for p in pts) / len(pts)
            # Convert rings to [lat, lon] format for Leaflet
            leaflet_rings = [[[p[1], p[0]] for p in ring] for ring in rings]
            results[pid] = {
                "lat": lat,
                "lon": lon,
                "rings": leaflet_rings,
            }
    return results


def generate_html(rows: list[dict], output_path: Path):
    """Generate an interactive HTML parcel viewer with Leaflet maps and parcel boundaries."""
    html = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sara Holt - R2 Vacant Parcel Viewer</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; }
  .header { background: #16213e; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f3460; }
  .header h1 { font-size: 18px; color: #e94560; }
  .header .nav { display: flex; gap: 8px; align-items: center; }
  .header button { background: #0f3460; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; }
  .header button:hover { background: #e94560; }
  .header .counter { color: #aaa; font-size: 14px; }
  .container { display: grid; grid-template-columns: 380px 1fr; height: calc(100vh - 52px); }
  .sidebar { overflow-y: auto; background: #16213e; border-right: 2px solid #0f3460; }
  .parcel-card { padding: 10px 14px; border-bottom: 1px solid #0f3460; cursor: pointer; transition: background 0.15s; }
  .parcel-card:hover { background: #1a1a3e; }
  .parcel-card.active { background: #0f3460; border-left: 3px solid #e94560; }
  .parcel-card .pid { font-weight: 600; color: #e94560; font-size: 13px; }
  .parcel-card .addr { font-size: 14px; margin: 2px 0; }
  .parcel-card .owner { font-size: 12px; color: #aaa; }
  .parcel-card .stats { display: flex; gap: 8px; margin-top: 4px; font-size: 11px; flex-wrap: wrap; }
  .parcel-card .stats span { background: #1a1a2e; padding: 2px 6px; border-radius: 3px; }
  .parcel-card .tier-a { color: #4ade80; }
  .parcel-card .tier-b { color: #fbbf24; }
  .main { display: flex; flex-direction: column; }
  .info-bar { background: #16213e; padding: 10px 20px; display: flex; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid #0f3460; align-items: center; }
  .info-item { font-size: 12px; }
  .info-item .label { color: #888; text-transform: uppercase; font-size: 10px; }
  .info-item .value { font-size: 13px; font-weight: 600; }
  .map-container { flex: 1; position: relative; }
  #map { width: 100%; height: 100%; }
  .map-buttons { position: absolute; top: 10px; right: 10px; z-index: 1000; display: flex; gap: 6px; }
  .map-buttons a, .map-buttons button { background: #fff; color: #333; border: 2px solid rgba(0,0,0,0.2); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; text-decoration: none; }
  .map-buttons a:hover, .map-buttons button:hover { background: #e94560; color: #fff; }
  .comp-bar { background: #16213e; padding: 10px 20px; border-top: 1px solid #0f3460; font-size: 12px; max-height: 100px; overflow-y: auto; }
  .comp-bar .comp-row { display: flex; gap: 16px; margin: 3px 0; }
  .comp-bar .comp-label { color: #e94560; font-weight: 600; min-width: 80px; }
  .links a { color: #60a5fa; font-size: 12px; text-decoration: none; margin-right: 12px; }
  .links a:hover { text-decoration: underline; }
  .rating-bar { background: #0f3460; padding: 8px 20px; display: flex; gap: 8px; align-items: center; border-top: 1px solid #1a1a2e; }
  .rating-bar button { padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 600; }
  .rate-yes { background: #4ade80; color: #000; }
  .rate-maybe { background: #fbbf24; color: #000; }
  .rate-no { background: #f87171; color: #000; }
  .rate-skip { background: #64748b; color: #fff; }
  .filter-bar { padding: 8px 12px; background: #1a1a2e; border-bottom: 1px solid #0f3460; display: flex; gap: 8px; }
  .filter-bar select, .filter-bar input { background: #0f3460; color: #fff; border: 1px solid #1a1a2e; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
  .filter-bar input { flex: 1; }
  .kbd { background: #333; color: #aaa; padding: 1px 5px; border-radius: 3px; font-size: 11px; font-family: monospace; }
</style>
</head>
<body>
<div class="header">
  <h1>R2 Vacant Land - Hamilton County</h1>
  <div class="nav">
    <button onclick="prev()">&#9664; Prev</button>
    <span class="counter" id="counter">1 / 0</span>
    <button onclick="next()">Next &#9654;</button>
    <button onclick="exportRatings()">Export Ratings CSV</button>
  </div>
</div>
<div class="container">
  <div class="sidebar">
    <div class="filter-bar">
      <select id="ratingFilter" onchange="applyFilter()">
        <option value="all">All</option>
        <option value="unrated">Unrated</option>
        <option value="yes">Yes</option>
        <option value="maybe">Maybe</option>
        <option value="no">No</option>
      </select>
      <input type="text" id="searchBox" placeholder="Search address/owner..." oninput="applyFilter()">
    </div>
    <div id="parcelList"></div>
  </div>
  <div class="main">
    <div class="info-bar" id="infoBar"></div>
    <div class="map-container">
      <div id="map"></div>
      <div class="map-buttons">
        <a id="streetViewBtn" href="#" target="_blank">Street View</a>
        <a id="googleMapsBtn" href="#" target="_blank">Google Maps</a>
        <a id="assessorBtn" href="#" target="_blank">Assessor Card</a>
      </div>
    </div>
    <div class="comp-bar" id="compBar"></div>
    <div class="rating-bar">
      <span style="color:#aaa;font-size:12px;">Rate:</span>
      <button class="rate-yes" onclick="rate('yes')"><span class="kbd">1</span> Yes</button>
      <button class="rate-maybe" onclick="rate('maybe')"><span class="kbd">2</span> Maybe</button>
      <button class="rate-no" onclick="rate('no')"><span class="kbd">3</span> No</button>
      <button class="rate-skip" onclick="rate('skip'); next()"><span class="kbd">Space</span> Skip</button>
    </div>
  </div>
</div>
<script>
const parcels = PARCEL_DATA_PLACEHOLDER;

let ratings = JSON.parse(localStorage.getItem('parcelRatings') || '{}');
let filtered = [...Array(parcels.length).keys()];
let currentIdx = 0;

// Initialize Leaflet map
const map = L.map('map', { zoomControl: true });
const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
  attribution: 'Esri', maxZoom: 20
});
const streets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: 'OSM', maxZoom: 19
});
const hybrid = L.layerGroup([
  satellite,
  L.tileLayer('https://stamen-tiles.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}.png', { maxZoom: 20, opacity: 0.7 })
]);
satellite.addTo(map);
L.control.layers({ 'Satellite': satellite, 'Street': streets }, null, { position: 'bottomleft' }).addTo(map);

let parcelLayer = null;

function applyFilter() {
  const rf = document.getElementById('ratingFilter').value;
  const search = document.getElementById('searchBox').value.toLowerCase();
  filtered = [];
  for (let i = 0; i < parcels.length; i++) {
    const p = parcels[i];
    const r = ratings[p.parcel_id] || 'unrated';
    if (rf !== 'all' && r !== rf) continue;
    if (search && !(p.address + ' ' + p.owner + ' ' + p.parcel_id).toLowerCase().includes(search)) continue;
    filtered.push(i);
  }
  currentIdx = 0;
  renderList();
  if (filtered.length > 0) showParcel(filtered[0]);
}

function renderList() {
  const list = document.getElementById('parcelList');
  list.innerHTML = filtered.map((i, fi) => {
    const p = parcels[i];
    const r = ratings[p.parcel_id] || '';
    const rDot = r === 'yes' ? '&#x1f7e2;' : r === 'maybe' ? '&#x1f7e1;' : r === 'no' ? '&#x1f534;' : '';
    const tierClass = (p.deal_tier||'').startsWith('A') ? 'tier-a' : 'tier-b';
    return `<div class="parcel-card ${fi === currentIdx ? 'active' : ''}" onclick="currentIdx=${fi};showParcel(${i});renderList()">
      <div class="pid">${rDot} ${p.parcel_id}</div>
      <div class="addr">${p.address || 'No address'}</div>
      <div class="owner">${p.owner}</div>
      <div class="stats">
        <span>${p.calc_acres}ac</span>
        <span>App $${Number(p.appraised_value).toLocaleString()}</span>
        <span>Land ${p.land_est_value ? '$'+Number(p.land_est_value).toLocaleString() : '?'}</span>
        <span>ARV ${p.arv_comp_median ? '$'+Number(p.arv_comp_median).toLocaleString() : '?'}</span>
        <span class="${tierClass}">${(p.deal_tier||'').split(' ')[0]}</span>
      </div>
    </div>`;
  }).join('');
  document.getElementById('counter').textContent = `${currentIdx + 1} / ${filtered.length}`;
  // Scroll active card into view
  const active = document.querySelector('.parcel-card.active');
  if (active) active.scrollIntoView({ block: 'nearest' });
}

function showParcel(i) {
  const p = parcels[i];

  // Info bar
  document.getElementById('infoBar').innerHTML = `
    <div class="info-item"><div class="label">Address</div><div class="value">${p.address || 'N/A'}</div></div>
    <div class="info-item"><div class="label">Owner</div><div class="value">${p.owner}</div></div>
    <div class="info-item"><div class="label">Mailing</div><div class="value">${p.owner_mailing || ''}</div></div>
    <div class="info-item"><div class="label">Acres</div><div class="value">${p.calc_acres}</div></div>
    <div class="info-item"><div class="label">Appraised</div><div class="value">$${Number(p.appraised_value).toLocaleString()}</div></div>
    <div class="info-item"><div class="label">Land Est</div><div class="value">${p.land_est_value ? '$'+Number(p.land_est_value).toLocaleString() : 'N/A'}</div></div>
    <div class="info-item"><div class="label">ARV Median</div><div class="value">${p.arv_comp_median ? '$'+Number(p.arv_comp_median).toLocaleString() : 'N/A'}</div></div>
    <div class="info-item"><div class="label">Water</div><div class="value">${p.water_provider || 'None'}</div></div>
    <div class="info-item"><div class="label">Sewer</div><div class="value">${p.sewer_provider || 'None'}</div></div>
    <div class="info-item"><div class="label">Tier</div><div class="value">${p.deal_tier || ''}</div></div>
  `;

  // Update external link buttons
  document.getElementById('streetViewBtn').href = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${p.lat},${p.lon}&heading=0&pitch=0&fov=90`;
  document.getElementById('googleMapsBtn').href = `https://www.google.com/maps/@${p.lat},${p.lon},18z/data=!3m1!1e1`;
  document.getElementById('assessorBtn').href = p.assessor_link || '#';

  // Draw parcel on map
  if (parcelLayer) map.removeLayer(parcelLayer);

  if (p.rings && p.rings.length > 0) {
    parcelLayer = L.polygon(p.rings, {
      color: '#e94560',
      weight: 3,
      fillColor: '#e94560',
      fillOpacity: 0.25,
      dashArray: null
    }).addTo(map);
    map.fitBounds(parcelLayer.getBounds(), { padding: [80, 80], maxZoom: 18 });
  } else if (p.lat && p.lon) {
    parcelLayer = L.circleMarker([parseFloat(p.lat), parseFloat(p.lon)], {
      radius: 12, color: '#e94560', fillColor: '#e94560', fillOpacity: 0.4
    }).addTo(map);
    map.setView([parseFloat(p.lat), parseFloat(p.lon)], 17);
  }

  // Comp details
  document.getElementById('compBar').innerHTML = `
    <div class="comp-row"><span class="comp-label">Land (${p.land_comp_count || 0}, ${p.land_comp_radius || 'none'}):</span><span>${p.land_comp_details || 'None found'}</span></div>
    <div class="comp-row"><span class="comp-label">ARV (${p.arv_comp_count || 0}, ${p.arv_comp_radius || 'none'}):</span><span>${p.arv_comp_details || 'None found'}</span></div>
  `;
  document.getElementById('counter').textContent = `${currentIdx + 1} / ${filtered.length}`;
}

function next() { if (currentIdx < filtered.length - 1) { currentIdx++; showParcel(filtered[currentIdx]); renderList(); } }
function prev() { if (currentIdx > 0) { currentIdx--; showParcel(filtered[currentIdx]); renderList(); } }

function rate(r) {
  const p = parcels[filtered[currentIdx]];
  ratings[p.parcel_id] = r;
  localStorage.setItem('parcelRatings', JSON.stringify(ratings));
  renderList();
}

function exportRatings() {
  const fields = ['parcel_id','address','owner','owner_mailing','rating','calc_acres','appraised_value','land_est_value','arv_comp_median','water_provider','sewer_provider','deal_tier','lat','lon','assessor_link'];
  let csv = fields.join(',') + '\n';
  for (const p of parcels) {
    const r = ratings[p.parcel_id] || 'unrated';
    csv += fields.map(f => f === 'rating' ? `"${r}"` : `"${(p[f]||'').toString().replace(/"/g,'""')}"`).join(',') + '\n';
  }
  const blob = new Blob([csv], {type: 'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'parcel_ratings.csv';
  a.click();
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); next(); }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); prev(); }
  if (e.key === '1') rate('yes');
  if (e.key === '2') rate('maybe');
  if (e.key === '3') rate('no');
  if (e.key === ' ') { e.preventDefault(); rate('skip'); next(); }
});

applyFilter();
if (filtered.length > 0) showParcel(filtered[0]);
</script>
</body>
</html>"""
    parcel_json = json.dumps(rows, indent=None)
    html = html.replace("PARCEL_DATA_PLACEHOLDER", parcel_json)
    output_path.write_text(html, encoding="utf-8")


def main():
    if not INPUT_CSV.exists():
        print(f"Waiting for comps to finish... {INPUT_CSV} not found yet.")
        print("Run this after comp_parcels.py completes.")
        sys.exit(1)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Adding map links and geometries for {len(rows)} parcels...\n")

    # Batch fetch full geometries in WGS84
    all_pids = [r["parcel_id"] for r in rows]
    geom_data = {}
    batch_size = 50
    for i in range(0, len(all_pids), batch_size):
        batch = all_pids[i:i + batch_size]
        g = get_geometries_batch(batch)
        geom_data.update(g)
        print(f"  Batch {i // batch_size + 1}: got {len(g)} geometries (total: {len(geom_data)})")
        time.sleep(0.2)

    print(f"\nGot geometries for {len(geom_data)}/{len(rows)} parcels")

    # Add geometry + links to each row
    new_fields = fieldnames + ["lat", "lon", "google_maps", "street_view"]
    for r in rows:
        pid = r["parcel_id"]
        if pid in geom_data:
            gd = geom_data[pid]
            r["lat"] = f"{gd['lat']:.6f}"
            r["lon"] = f"{gd['lon']:.6f}"
            r["rings"] = gd["rings"]
            r["google_maps"] = f"https://www.google.com/maps/@{gd['lat']:.6f},{gd['lon']:.6f},18z/data=!3m1!1e1"
            r["street_view"] = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={gd['lat']:.6f},{gd['lon']:.6f}"
        else:
            r["lat"] = r["lon"] = r["google_maps"] = r["street_view"] = ""
            r["rings"] = []

    # Write CSV (without rings - too large for CSV)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUTPUT_CSV.name}")

    # Generate HTML viewer (with rings for map display)
    generate_html(rows, OUTPUT_HTML)
    print(f"Wrote {OUTPUT_HTML.name}")
    print(f"\nOpen in browser: file:///{OUTPUT_HTML.as_posix()}")


if __name__ == "__main__":
    main()
