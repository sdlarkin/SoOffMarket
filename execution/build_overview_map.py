"""
Build an overview map showing all filtered parcels on a single wide-view map.
Color-coded by duplex grade + geographic priority.
Click any parcel for details popup.
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp" / "sara_holt_segments"


def main():
    # Load parcel data from viewer
    html = (TMP_DIR / "parcel_viewer.html").read_text(encoding="utf-8")
    start = html.index("const parcels = ") + len("const parcels = ")
    end = html.index(";\n", start)
    parcels = json.loads(html[start:end])
    print(f"Loaded {len(parcels)} parcels")

    template = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sara Holt - Overview Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  #map { width: 100vw; height: 100vh; }
  .legend {
    background: rgba(22,33,62,0.95); color: #e0e0e0; padding: 12px 16px;
    border-radius: 8px; font-size: 13px; line-height: 1.8;
  }
  .legend h3 { color: #e94560; margin-bottom: 6px; font-size: 14px; }
  .legend .dot {
    display: inline-block; width: 12px; height: 12px;
    border-radius: 50%; margin-right: 6px; vertical-align: middle;
  }
  .info-popup { font-size: 13px; line-height: 1.6; min-width: 280px; }
  .info-popup .title { font-weight: 700; font-size: 14px; color: #e94560; margin-bottom: 4px; }
  .info-popup .row { display: flex; justify-content: space-between; gap: 12px; }
  .info-popup .label { color: #888; }
  .info-popup .links { margin-top: 8px; display: flex; gap: 10px; }
  .info-popup .links a { color: #2563eb; text-decoration: none; font-weight: 600; }
  .info-popup .links a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div id="map"></div>
<script>
const parcels = %%PARCEL_DATA%%;

const map = L.map('map', { zoomControl: true });

const satellite = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  { attribution: 'Esri', maxZoom: 20 }
);
const streets = L.tileLayer(
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  { attribution: 'OSM', maxZoom: 19 }
);
const roadLabels = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}',
  { maxZoom: 20, opacity: 0.7 }
);

satellite.addTo(map);
roadLabels.addTo(map);
L.control.layers(
  { 'Satellite': satellite, 'Street': streets },
  { 'Road Labels': roadLabels },
  { position: 'topright' }
).addTo(map);

function getColor(p) {
  const grade = (p.duplex_friendliness || '').charAt(0);
  const geo = p.geo_priority || '';
  if (geo.startsWith('1')) {
    return grade === 'A' ? '#22c55e' : '#86efac';
  } else if (geo.startsWith('2')) {
    return grade === 'A' ? '#3b82f6' : '#93c5fd';
  } else {
    return grade === 'A' ? '#f59e0b' : '#fcd34d';
  }
}

function getRadius(p) {
  const acres = parseFloat(p.computed_acres || p.calc_acres || 0.5);
  return Math.max(8, Math.min(18, acres * 10));
}

function makePopup(p) {
  const lat = parseFloat(p.lat);
  const lon = parseFloat(p.lon);
  const grade = (p.duplex_friendliness || '').split(' - ');
  const geo = (p.geo_priority || '').split(' - ');
  const acres = p.computed_acres || p.calc_acres || '?';
  const fmt = v => v ? '$' + Number(v).toLocaleString() : '?';
  return '<div class="info-popup">'
    + '<div class="title">' + p.parcel_id + ' - ' + (p.address || 'No address') + '</div>'
    + '<div class="row"><span class="label">Owner:</span> ' + p.owner + '</div>'
    + '<div class="row"><span class="label">Mailing:</span> ' + (p.owner_mailing || '') + '</div>'
    + '<div class="row"><span class="label">Area:</span> ' + (geo[1] || '?') + '</div>'
    + '<div class="row"><span class="label">Acres:</span> ' + acres + '</div>'
    + '<div class="row"><span class="label">Appraised:</span> ' + fmt(p.appraised_value) + '</div>'
    + '<div class="row"><span class="label">Land Est:</span> ' + fmt(p.land_est_value) + '</div>'
    + '<div class="row"><span class="label">ARV Median:</span> ' + fmt(p.arv_comp_median) + '</div>'
    + '<div class="row"><span class="label">Duplex:</span> <b>' + (grade[0]||'?') + '</b> - ' + (grade[1]||'') + ' (' + (p.duplex_ratio||'0') + '% multi)</div>'
    + '<div class="row"><span class="label">Water:</span> ' + (p.water_provider || 'N/A') + '</div>'
    + '<div class="row"><span class="label">Sewer:</span> ' + (p.sewer_provider || 'N/A') + '</div>'
    + '<div class="links">'
    + '<a href="' + (p.assessor_link||'#') + '" target="_blank">Assessor</a>'
    + '<a href="https://www.google.com/maps/@' + lat + ',' + lon + ',18z/data=!3m1!1e1" target="_blank">Google Maps</a>'
    + '<a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=' + lat + ',' + lon + '&heading=0&pitch=0&fov=90" target="_blank">Street View</a>'
    + '</div></div>';
}

const bounds = [];

parcels.forEach(p => {
  const lat = parseFloat(p.lat);
  const lon = parseFloat(p.lon);
  if (!lat || !lon) return;
  bounds.push([lat, lon]);

  const color = getColor(p);
  const popup = makePopup(p);
  const acres = p.computed_acres || p.calc_acres || '?';
  const grade = (p.duplex_friendliness || '').charAt(0);
  const fmt = v => v ? '$' + Number(v).toLocaleString() : '?';

  // Draw parcel polygon
  if (p.rings && p.rings.length > 0) {
    L.polygon(p.rings, {
      color: color, weight: 2, fillColor: color, fillOpacity: 0.4
    }).addTo(map).bindPopup(popup);
  }

  // Circle marker for zoom-out visibility
  L.circleMarker([lat, lon], {
    radius: getRadius(p),
    color: '#fff', weight: 2,
    fillColor: color, fillOpacity: 0.85
  }).addTo(map)
    .bindTooltip(
      (p.address || p.parcel_id) + '<br>'
      + acres + 'ac | ' + fmt(p.appraised_value) + ' | ' + grade,
      { direction: 'top', offset: [0, -8] }
    )
    .bindPopup(popup);
});

if (bounds.length > 0) {
  map.fitBounds(bounds, { padding: [50, 50] });
}

// Legend
const legend = L.control({ position: 'bottomleft' });
legend.onAdd = function() {
  const div = L.DomUtil.create('div', 'legend');
  div.innerHTML = '<h3>R2 Vacant Parcels (' + parcels.length + ')</h3>'
    + '<div><span class="dot" style="background:#22c55e"></span> A - Ooltewah/Collegedale</div>'
    + '<div><span class="dot" style="background:#86efac"></span> B - Ooltewah/Collegedale</div>'
    + '<div><span class="dot" style="background:#3b82f6"></span> A - East Chattanooga</div>'
    + '<div><span class="dot" style="background:#93c5fd"></span> B - East Chattanooga</div>'
    + '<div><span class="dot" style="background:#f59e0b"></span> A - West Chattanooga</div>'
    + '<div><span class="dot" style="background:#fcd34d"></span> B - West Chattanooga</div>'
    + '<div style="margin-top:6px;color:#aaa;font-size:11px;">Dot size = acreage. Click for details.</div>';
  return div;
};
legend.addTo(map);
</script>
</body>
</html>'''

    output = template.replace('%%PARCEL_DATA%%', json.dumps(parcels))
    out_path = TMP_DIR / "overview_map.html"
    out_path.write_text(output, encoding="utf-8")
    print(f"Wrote {out_path.name}")
    print(f"Open: file:///{out_path.as_posix()}")


if __name__ == "__main__":
    main()
