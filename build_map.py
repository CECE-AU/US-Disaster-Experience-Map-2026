import base64
import csv
import json
import math
import os

# ==============================================================================
# 1. CONFIGURATION: Update your 2026 and 2025 CSV filenames here
# ==============================================================================
CSV_2026 = 'States Climate Disasters_Data26.csv'       # Your October 2026 CSV
CSV_2025 = 'States Climate Disasters_Data25.csv'  # Your 2025 CSV (same column structure)
LOGO_FILENAME = 'CECE logo color (1).png'

# 'point' = 2026% - 2025% (percentage point difference)
# 'relative' = ((2026% - 2025%) / 2025%) * 100 (relative percent change)
CHANGE_TYPE = 'point'

# ==============================================================================
# 2. STATE LOOKUPS & METRIC DEFINITIONS
# ==============================================================================
state_to_code = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'District of Columbia': 'DC',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL',
    'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
    'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR',
    'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD',
    'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA',
    'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'
}
code_to_state = {v: k for k, v in state_to_code.items()}

metrics = {
    'Overall (Any Disaster)': (
        'Experienced Disaster',
        'Total Count',
        'Any Climate-Related Disaster',
        ['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026']  # Yellow to Red
    ),
    'Extreme Heat': (
        'Extreme Heat',
        'Count of Response to Extreme Heat',
        'Extreme Heat',
        ['#feedde', '#fdbe85', '#fd8d3c', '#e6550d', '#a63603']  # Orange Light to Dark
    ),
    'Flooding / Sea Level': (
        'Severe flooding and/or rising sea levels',
        'Count of Response to Severe flooding and/or rising sea levels',
        'Severe Flooding And/Or Rising Sea Levels',
        ['#e0f3ff', '#80ccff', '#1aa3ff', '#0073e6', '#004080']  # Blue Bright
    ),
    'Drought / Water': (
        'Severe drought, water shortages',
        'Count of Response to Severe drought, water shortages',
        'Severe Drought, Water Shortages',
        ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c']  # Blue Light to Dark
    ),
    'Wildfires / Smoke': (
        'Wildfires, smoke from wildfires',
        'Count of Response to Wildfires, smoke from wildfires',
        'Wildfires, Smoke From Wildfires',
        ['#f6e8c3', '#dfc27d', '#bf812d', '#8c510a', '#543005']  # Brown Light to Dark
    ),
    'Powerful Storms': (
        'More frequent powerful storms (hurricanes, typhoons, tornadoes)',
        'Count of Response to More frequent powerful storms (hurricanes, typhoons, tornadoes)',
        'More Frequent Powerful Storms (Hurricanes, Typhoons, Tornadoes)',
        ['#e0f3db', '#a8ddb5', '#4eb3d3', '#2b8cbe', '#084081']  # Cyan-Light to Blue-Dark
    )
}

# Smooth Continuous Diverging Colorscale for Percentage Point Shift (-50% to +50%)
CONTINUOUS_CHANGE_COLORSCALE = [
    [0.0,  '#2166ac'],  # -50% (Deep Blue)
    [0.25, '#67a9cf'],  # -25% (Light Blue)
    [0.5,  '#f7f7f7'],  #   0% (Neutral White/Grey)
    [0.75, '#ef8a62'],  # +25% (Light Red/Orange)
    [1.0,  '#b2182b']   # +50% (Deep Red)
]

def make_discrete_colorscale(colors_5):
    return [
        [0.0, colors_5[0]], [0.2, colors_5[0]],
        [0.2, colors_5[1]], [0.4, colors_5[1]],
        [0.4, colors_5[2]], [0.6, colors_5[2]],
        [0.6, colors_5[3]], [0.8, colors_5[3]],
        [0.8, colors_5[4]], [1.0, colors_5[4]]
    ]

# ==============================================================================
# 3. PURE PYTHON CSV LOADER, LOGO ENCODER & POOLED JENKS CLASSIFIER
# ==============================================================================
def get_logo_src():
    """Embeds the logo as Base64 if present locally so index.html is 100% self-contained."""
    candidates = [LOGO_FILENAME, 'CECE logo color.png', 'logo.png']
    for fname in candidates:
        if os.path.exists(fname):
            with open(fname, 'rb') as img_f:
                b64 = base64.b64encode(img_f.read()).decode('utf-8')
            print(f"Embedded logo '{fname}' directly into index.html.")
            return f"data:image/png;base64,{b64}"
    print(f"NOTE: '{LOGO_FILENAME}' not found in folder yet; linking by filename '{LOGO_FILENAME}'.")
    return LOGO_FILENAME

def load_and_clean_csv(filepath):
    rows_by_code = {}
    with open(filepath, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k}
            st_raw = row.get('State', '')
            code = st_raw.upper() if len(st_raw) == 2 else state_to_code.get(st_raw, st_raw)
            if code in code_to_state:
                row['State_Code'] = code
                row['State_Full'] = code_to_state[code]
                rows_by_code[code] = row
    return [rows_by_code[c] for c in sorted(rows_by_code.keys())]

def parse_num(val):
    if val is None or val == '':
        return 0.0
    s = str(val).replace('%', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def get_percentage_and_count(rows, val_col, count_col):
    has_pct_sign = any('%' in str(r.get(val_col, '')) for r in rows)
    vals = [parse_num(r.get(val_col, 0)) for r in rows]
    counts = [int(round(parse_num(r.get(count_col, 0)))) for r in rows]
    max_val = max(vals) if vals else 0.0
    all_int_le_count = all((v % 1 == 0) and (v <= c) for v, c in zip(vals, counts) if c > 0)

    pcts = []
    for v, c in zip(vals, counts):
        if has_pct_sign:
            pcts.append(round(v, 1))
        elif max_val <= 1.0:
            pcts.append(round(v * 100.0, 1))
        elif all_int_le_count:
            pcts.append(round((v / c) * 100.0, 1) if c > 0 else 0.0)
        else:
            pcts.append(round(v, 1))
    return pcts, counts

def fisher_jenks_breaks(values, k=5):
    clean_vals = sorted([v for v in values if v is not None and not math.isnan(v)])
    uniq = sorted(list(set(clean_vals)))
    if len(uniq) <= k:
        mn, mx = (clean_vals[0], clean_vals[-1]) if clean_vals else (0.0, 100.0)
        step = (mx - mn) / k if k > 0 else 1.0
        return [round(mn + i * step, 1) for i in range(k + 1)]

    n = len(clean_vals)
    mat1 = [[0] * (k + 1) for _ in range(n + 1)]
    mat2 = [[float('inf')] * (k + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        mat1[i][1] = 1
        mat2[i][1] = 0.0

    for l in range(2, n + 1):
        s1 = s2 = w = 0.0
        v = 0.0
        for m in range(1, l + 1):
            i3 = l - m + 1
            val = clean_vals[i3 - 1]
            s2 += val * val
            s1 += val
            w += 1.0
            v = s2 - (s1 * s1) / w
            i4 = i3 - 1
            if i4 != 0:
                for j in range(2, k + 1):
                    if mat2[l][j] >= (v + mat2[i4][j - 1]):
                        mat1[l][j] = i3
                        mat2[l][j] = v + mat2[i4][j - 1]
        mat1[l][1] = 1
        mat2[l][1] = v

    kclass = [0.0] * (k + 1)
    kclass[k] = clean_vals[-1]
    kclass[0] = clean_vals[0]
    count_num = k
    k_idx = n
    while count_num >= 2:
        idx = int(mat1[k_idx][count_num]) - 2
        kclass[count_num - 1] = clean_vals[max(0, idx)]
        k_idx = int(mat1[k_idx][count_num] - 1)
        count_num -= 1

    for i in range(1, len(kclass)):
        if kclass[i] <= kclass[i - 1]:
            higher = [u for u in uniq if u > kclass[i - 1]]
            kclass[i] = higher[0] if higher else round(kclass[i - 1] + 0.1, 1)

    return [round(x, 1) for x in kclass]

def assign_bin(val, breaks):
    for i in range(len(breaks) - 1):
        if val <= breaks[i + 1] or i == len(breaks) - 2:
            return float(i)
    return 0.0

def format_break_labels(breaks):
    labels = []
    for i in range(5):
        low = breaks[i] if i == 0 else round(breaks[i] + 0.1, 1)
        high = breaks[i + 1]
        if low > high:
            low = high
        labels.append(f"{low:.1f}% – {high:.1f}%")
    return labels

# ==============================================================================
# 4. STATE CENTERS & SMALL-STATE LEADER LINES
# ==============================================================================
state_centers = {
    'AL': (32.7, -86.8), 'AK': (63.5, -152.0), 'AZ': (34.3, -111.7), 'AR': (34.9, -92.4),
    'CA': (37.2, -119.6), 'CO': (39.0, -105.5), 'FL': (28.6, -81.7), 'GA': (32.7, -83.4),
    'HI': (20.8, -156.3), 'ID': (44.4, -114.6), 'IL': (40.0, -89.2), 'IN': (39.9, -86.3),
    'IA': (42.1, -93.5), 'KS': (38.5, -98.3), 'KY': (37.5, -85.3), 'LA': (31.1, -92.0),
    'ME': (45.3, -69.2), 'MI': (43.4, -84.8), 'MN': (46.2, -94.3), 'MS': (32.7, -89.7),
    'MO': (38.4, -92.5), 'MT': (47.0, -109.6), 'NE': (41.5, -99.8), 'NV': (39.3, -116.6),
    'NM': (34.4, -106.1), 'NY': (42.9, -75.5), 'NC': (35.5, -79.4), 'ND': (47.4, -100.5),
    'OH': (40.3, -82.8), 'OK': (35.6, -97.5), 'OR': (43.9, -120.6), 'PA': (40.9, -77.8),
    'SC': (33.9, -80.9), 'SD': (44.4, -100.2), 'TN': (35.8, -86.4), 'TX': (31.5, -99.3),
    'UT': (39.3, -111.7), 'VA': (37.5, -78.8), 'WA': (47.4, -120.5), 'WV': (38.6, -80.6),
    'WI': (44.6, -89.7), 'WY': (43.0, -107.5)
}

small_states_leaders = {
    'VT': (44.0, -72.7, 45.8, -71.3, 'top center'),
    'NH': (43.7, -71.6, 44.3, -68.3, 'middle right'),
    'MA': (42.2, -71.8, 42.6, -68.1, 'middle right'),
    'RI': (41.7, -71.5, 41.2, -68.3, 'middle right'),
    'CT': (41.6, -72.7, 39.8, -69.1, 'middle right'),
    'NJ': (40.1, -74.7, 38.6, -70.3, 'middle right'),
    'DE': (39.0, -75.5, 37.3, -71.1, 'middle right'),
    'MD': (39.0, -76.8, 36.0, -71.9, 'middle right'),
    'DC': (38.9, -77.0, 34.7, -72.7, 'middle right')
}

# ==============================================================================
# 5. LOAD DATASETS & PRECOMPUTE ALL COMBINATIONS
# ==============================================================================
rows_2026 = load_and_clean_csv(CSV_2026)

if os.path.exists(CSV_2025):
    raw_2025 = {r['State_Code']: r for r in load_and_clean_csv(CSV_2025)}
    rows_2025 = [raw_2025.get(r['State_Code'], r) for r in rows_2026]
    has_separate_2025 = True
    print(f"Loaded both {CSV_2026} and {CSV_2025} successfully.")
else:
    print(f"NOTE: '{CSV_2025}' not found in folder. Using 2026 data as placeholder for 2025 until '{CSV_2025}' is added.")
    rows_2025 = [dict(r) for r in rows_2026]
    has_separate_2025 = False

state_codes = [r['State_Code'] for r in rows_2026]
state_names = [r['State_Full'] for r in rows_2026]
code_to_idx = {c: i for i, c in enumerate(state_codes)}
logo_src = get_logo_src()

present_codes = set(state_codes)
leader_lats, leader_lons = [], []
callout_lats, callout_lons, callout_texts, callout_positions = [], [], [], []

for code, (s_lat, s_lon, l_lat, l_lon, t_pos) in small_states_leaders.items():
    if code in present_codes:
        leader_lats.extend([s_lat, l_lat, None])
        leader_lons.extend([s_lon, l_lon, None])
        callout_lats.append(l_lat)
        callout_lons.append(l_lon)
        callout_texts.append(f" {code}" if t_pos == 'middle right' else code)
        callout_positions.append(t_pos)

center_codes = [code for code in state_centers.keys() if code in present_codes]
center_lats = [state_centers[code][0] for code in center_codes]
center_lons = [state_centers[code][1] for code in center_codes]
center_texts = center_codes

def get_center_label_colors(z_vals, is_change=False):
    """Returns white (#ffffff) for dark state fills and dark (#111827) for light state fills."""
    colors = []
    for code in center_codes:
        val = z_vals[code_to_idx[code]]
        if not is_change:
            # Bins 3 and 4 are the two darkest colors in the 5-class ramp
            colors.append('#ffffff' if val >= 3.0 else '#111827')
        else:
            # Beyond +/- 25 percentage points on the -50 to +50 continuous ramp
            colors.append('#ffffff' if abs(val) >= 25.0 else '#111827')
    return colors

fixed_breaks = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
fixed_labels = ['0.0% – 20.0%', '20.1% – 40.0%', '40.1% – 60.0%', '60.1% – 80.0%', '80.1% – 100.0%']

views_data = {}

for metric_key, (val_col, count_col, q_text, hex_ramp) in metrics.items():
    pct_26, cnt_26 = get_percentage_and_count(rows_2026, val_col, count_col)
    pct_25, cnt_25 = get_percentage_and_count(rows_2025, val_col, count_col)

    # Pool 2025 and 2026 values together so Natural Breaks (Jenks) are locked across both years
    pooled_series = (pct_26 + pct_25) if has_separate_2025 else pct_26
    pooled_jenks_breaks = fisher_jenks_breaks(pooled_series, k=5)
    labels_jenks = format_break_labels(pooled_jenks_breaks)

    pct_chg = []
    for p26, p25 in zip(pct_26, pct_25):
        if CHANGE_TYPE == 'relative':
            chg = round(((p26 - p25) / p25) * 100.0, 1) if p25 != 0 else 0.0
        else:
            chg = round(p26 - p25, 1)
        pct_chg.append(chg)

    chg_label_desc = "Relative % Change" if CHANGE_TYPE == 'relative' else "Percentage Point Shift"
    # Clip continuous z values to [-50, 50] for the -50% to +50% scale
    pct_chg_clipped = [max(-50.0, min(50.0, v)) for v in pct_chg]

    views_data[metric_key] = {
        'question_text': q_text,
        'colorscale_year': make_discrete_colorscale(hex_ramp),
        'colorscale_change': CONTINUOUS_CHANGE_COLORSCALE,
        'datasets': {}
    }

    for yr_key, series_pct in [('2026', pct_26), ('2025', pct_25)]:
        bins_jenks = [assign_bin(v, pooled_jenks_breaks) for v in series_pct]
        bins_fixed = [assign_bin(v, fixed_breaks) for v in series_pct]

        customdata = [
            [s_name, float(p_val), int(c26), float(p25), float(p26), int(c25)]
            for s_name, p_val, c26, p25, p26, c25 in zip(state_names, series_pct, cnt_26, pct_25, pct_26, cnt_25)
        ]

        n_col_idx = 2 if yr_key == '2026' else 5
        hover_tmpl = (
            '<b>%{customdata[0]}</b> (' + yr_key + ')<br>'
            f'{q_text}: <b>%{{customdata[1]:.1f}}%</b><br>'
            f'Question Respondents: n = %{{customdata[{n_col_idx}]:,.0f}}'
            '<extra></extra>'
        )

        views_data[metric_key]['datasets'][yr_key] = {
            'jenks': {
                'z': bins_jenks, 'zmin': -0.5, 'zmax': 4.5,
                'tickvals': [0, 1, 2, 3, 4], 'ticktext': labels_jenks,
                'textcolors': get_center_label_colors(bins_jenks, is_change=False)
            },
            'fixed20': {
                'z': bins_fixed, 'zmin': -0.5, 'zmax': 4.5,
                'tickvals': [0, 1, 2, 3, 4], 'ticktext': fixed_labels,
                'textcolors': get_center_label_colors(bins_fixed, is_change=False)
            },
            'customdata': customdata,
            'hovertemplate': hover_tmpl,
            'legend_title': 'Experienced (%)'
        }

    customdata_chg = [
        [s_name, float(p_val), int(c26), float(p25), float(p26), int(c25)]
        for s_name, p_val, c26, p25, p26, c25 in zip(state_names, pct_chg, cnt_26, pct_25, pct_26, cnt_25)
    ]

    hover_tmpl_chg = (
        '<b>%{customdata[0]}</b> (2025 → 2026)<br>'
        f'{q_text}<br>'
        'Shift: <b>%{customdata[1]:+.1f} pts</b><br>'
        '2025: %{customdata[3]:.1f}% (n=%{customdata[5]:,.0f}) | '
        '2026: %{customdata[4]:.1f}% (n=%{customdata[2]:,.0f})'
        '<extra></extra>'
    )

    continuous_scale_obj = {
        'z': pct_chg_clipped,
        'zmin': -50.0,
        'zmax': 50.0,
        'tickvals': [-50, -25, 0, 25, 50],
        'ticktext': ['-50%', '-25%', '0%', '+25%', '+50%'],
        'textcolors': get_center_label_colors(pct_chg_clipped, is_change=True)
    }

    views_data[metric_key]['datasets']['change'] = {
        'jenks': continuous_scale_obj,
        'fixed20': continuous_scale_obj,
        'customdata': customdata_chg,
        'hovertemplate': hover_tmpl_chg,
        'legend_title': chg_label_desc
    }

# ==============================================================================
# 6. EXPORT COMPLETE INTERACTIVE HTML PAGE
# ==============================================================================
html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Experience with Disaster in the US</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    margin: 0;
    padding: 24px 32px;
    background-color: #ffffff;
    color: #111827;
  }}
  .dashboard-container {{
    max-width: 1200px;
    margin: 0 auto;
  }}
  .main-title {{
    font-size: 30px;
    font-weight: 800;
    color: #111827;
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
  }}
  .question-subtitle {{
    font-size: 17px;
    font-weight: 500;
    color: #374151;
    margin: 0 0 4px 0;
  }}
  .question-highlight {{
    font-weight: 700;
    color: #00a38d;
  }}
  .survey-subtext {{
    font-size: 13px;
    font-style: italic;
    color: #6b7280;
    margin: 0 0 18px 0;
  }}
  .subtext-note {{
    color: #dc2626;
    font-weight: 600;
    margin-left: 6px;
  }}
  .controls-wrapper {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
    justify-content: space-between;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 6px;
  }}
  .control-group {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }}
  .control-label {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6b7280;
    margin-right: 6px;
  }}
  .btn {{
    appearance: none;
    border: 1px solid #d1d5db;
    background: #ffffff;
    color: #374151;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  .btn:hover:not(:disabled) {{
    background: #f3f4f6;
    border-color: #9ca3af;
  }}
  .btn.active {{
    background: #1f2937;
    color: #ffffff;
    border-color: #1f2937;
    font-weight: 600;
  }}
  .btn:disabled, .btn.disabled {{
    background: #e5e7eb;
    color: #9ca3af;
    border-color: #d1d5db;
    cursor: not-allowed;
    opacity: 0.65;
  }}
  #disaster-map {{
    width: 100%;
    height: 580px;
  }}
  .dashboard-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-top: 4px;
    padding-top: 10px;
    border-top: 1px solid #f3f4f6;
  }}
  .footer-source {{
    font-size: 10.5px;
    font-style: italic;
    color: #6b7280;
    line-height: 1.4;
  }}
  .footer-logo {{
    height: 104px;
    width: auto;
    object-fit: contain;
    flex-shrink: 0;
  }}
</style>
</head>
<body>

<div class="dashboard-container">
  <h1 class="main-title">Experience with Disaster in the US</h1>
  <div class="question-subtitle" id="question-text">
    "Have You Personally Experienced <span class="question-highlight">Any Climate-Related Disaster</span> In The Last <span class="question-highlight">Twelve Months</span>?"
  </div>
  <div class="survey-subtext" id="survey-subtext">
    Nationally Representative Survey (n=1500), October 2026
  </div>

  <div class="controls-wrapper">
    <div class="control-group" id="metric-buttons">
      <span class="control-label">Disaster:</span>
      <button class="btn active" data-metric="Overall (Any Disaster)">Overall (Any Disaster)</button>
      <button class="btn" data-metric="Extreme Heat">Extreme Heat</button>
      <button class="btn" data-metric="Flooding / Sea Level">Flooding / Sea Level</button>
      <button class="btn" data-metric="Drought / Water">Drought / Water</button>
      <button class="btn" data-metric="Wildfires / Smoke">Wildfires / Smoke</button>
      <button class="btn" data-metric="Powerful Storms">Powerful Storms</button>
    </div>

    <div style="display:flex; flex-wrap:wrap; gap:18px;">
      <div class="control-group" id="year-buttons">
        <span class="control-label">Year:</span>
        <button class="btn active" data-year="2026">2026</button>
        <button class="btn" data-year="2025">2025</button>
        <button class="btn" data-year="change">Percentage Point Shift (2025–2026)</button>
      </div>

      <div class="control-group" id="scale-buttons">
        <span class="control-label">Breaks:</span>
        <button class="btn active" id="btn-jenks" data-scale="jenks">Natural Breaks (Jenks)</button>
        <button class="btn" id="btn-fixed" data-scale="fixed20">Interval/Scale</button>
      </div>
    </div>
  </div>

  <div id="disaster-map"></div>

  <div class="dashboard-footer">
    <div class="footer-source">
      Research Data: Surveys designed by CECE and administered with YouGov to a nationally representative sample (Oct 2025 &amp; 2026).
    </div>
    <img src="{logo_src}" alt="American University Center for Environment, Community & Equity" class="footer-logo" />
  </div>
</div>

<script>
  const STATE_CODES = {json.dumps(state_codes)};
  const VIEWS_DATA = {json.dumps(views_data)};
  const LEADER_LATS = {json.dumps(leader_lats)};
  const LEADER_LONS = {json.dumps(leader_lons)};
  const CENTER_LATS = {json.dumps(center_lats)};
  const CENTER_LONS = {json.dumps(center_lons)};
  const CENTER_TEXTS = {json.dumps(center_texts)};
  const CALLOUT_LATS = {json.dumps(callout_lats)};
  const CALLOUT_LONS = {json.dumps(callout_lons)};
  const CALLOUT_TEXTS = {json.dumps(callout_texts)};
  const CALLOUT_POSITIONS = {json.dumps(callout_positions)};

  let currentMetric = "Overall (Any Disaster)";
  let currentYear = "2026";
  let currentScale = "jenks";
  let savedYearScale = "jenks";

  const initMetricObj = VIEWS_DATA[currentMetric];
  const initDatasetObj = initMetricObj.datasets[currentYear];
  const initScaleObj = initDatasetObj[currentScale];

  // Trace 0: Choropleth
  const traceChoropleth = {{
    type: "choropleth",
    locations: STATE_CODES,
    z: initScaleObj.z,
    locationmode: "USA-states",
    colorscale: initMetricObj.colorscale_year,
    zmin: initScaleObj.zmin,
    zmax: initScaleObj.zmax,
    marker: {{ line: {{ color: "white", width: 1.2 }} }},
    customdata: initDatasetObj.customdata,
    colorbar: {{
      title: {{
        text: '<b>Experienced (%)</b><br><span style="font-size:11px;color:#6b7280">Natural Breaks (Jenks)</span>',
        font: {{ size: 13 }}
      }},
      tickvals: initScaleObj.tickvals,
      ticktext: initScaleObj.ticktext,
      len: 0.72,
      thickness: 20,
      outlinewidth: 0
    }},
    hovertemplate: initDatasetObj.hovertemplate
  }};

  // Trace 1: Leader lines stopping at callout anchor points
  const traceLeaders = {{
    type: "scattergeo",
    lat: LEADER_LATS,
    lon: LEADER_LONS,
    mode: "lines",
    line: {{ width: 1.1, color: "#4b5563" }},
    hoverinfo: "skip",
    showlegend: false
  }};

  // Trace 2: Centered state abbreviations (auto-contrasting white/black per state)
  const traceCenterLabels = {{
    type: "scattergeo",
    lat: CENTER_LATS,
    lon: CENTER_LONS,
    text: CENTER_TEXTS,
    mode: "text",
    textposition: "middle center",
    textfont: {{ family: "Arial, sans-serif", size: 10, color: initScaleObj.textcolors, weight: "bold" }},
    hoverinfo: "skip",
    showlegend: false
  }};

  // Trace 3: Offset callout abbreviations
  const traceCalloutLabels = {{
    type: "scattergeo",
    lat: CALLOUT_LATS,
    lon: CALLOUT_LONS,
    text: CALLOUT_TEXTS,
    mode: "text",
    textposition: CALLOUT_POSITIONS,
    textfont: {{ family: "Arial, sans-serif", size: 10, color: "#111827", weight: "bold" }},
    hoverinfo: "skip",
    showlegend: false
  }};

  const layout = {{
    dragmode: false,
    geo: {{
      scope: "usa",
      projection: {{ type: "albers usa" }},
      showlakes: false,
      showland: false,
      subunitcolor: "white",
      bgcolor: "rgba(0,0,0,0)"
    }},
    margin: {{ l: 10, r: 10, t: 10, b: 10 }},
    paper_bgcolor: "white",
    height: 580
  }};

  Plotly.newPlot("disaster-map", [traceChoropleth, traceLeaders, traceCenterLabels, traceCalloutLabels], layout, {{
    responsive: true,
    displayModeBar: false,
    scrollZoom: false,
    doubleClick: false
  }});

  // Block wheel zoom on the SVG geo layer while allowing normal page scrolling
  const mapEl = document.getElementById("disaster-map");
  mapEl.addEventListener("wheel", (e) => {{
    e.stopImmediatePropagation();
  }}, true);

  function updateDashboard() {{
    const btnJenks = document.getElementById("btn-jenks");
    const btnFixed = document.getElementById("btn-fixed");

    if (currentYear === "change") {{
      btnJenks.disabled = true;
      btnJenks.classList.add("disabled");
      btnJenks.classList.remove("active");
      btnFixed.classList.add("active");
      currentScale = "fixed20";
    }} else {{
      btnJenks.disabled = false;
      btnJenks.classList.remove("disabled");
      currentScale = savedYearScale;
      if (currentScale === "jenks") {{
        btnJenks.classList.add("active");
        btnFixed.classList.remove("active");
      }} else {{
        btnFixed.classList.add("active");
        btnJenks.classList.remove("active");
      }}
    }}

    const metricObj = VIEWS_DATA[currentMetric];
    const datasetObj = metricObj.datasets[currentYear];
    const scaleObj = datasetObj[currentScale];

    // 1. Update Question Subtitle (no brackets, #00a38d highlights, 6 vs 12 months)
    let monthsText = "Twelve Months";
    if (currentYear === "2025") {{
      monthsText = "Six Months";
    }} else if (currentYear === "change") {{
      monthsText = "Six / Twelve Months";
    }}

    const qEl = document.getElementById("question-text");
    qEl.innerHTML = `"Have You Personally Experienced <span class="question-highlight">${{metricObj.question_text}}</span> In The Last <span class="question-highlight">${{monthsText}}</span>?"`;

    // 2. Update Survey Subtext (with red warning note when Percentage Point Shift is active)
    const subEl = document.getElementById("survey-subtext");
    if (currentYear === "2026") {{
      subEl.innerHTML = "Nationally Representative Survey (n=1500), October 2026";
    }} else if (currentYear === "2025") {{
      subEl.innerHTML = "Nationally Representative Survey (n=1500), October 2025";
    }} else {{
      subEl.innerHTML = 'Comparison of Nationally Representative Surveys (October 2025 vs. October 2026, n=1500) <span class="subtext-note">Note: this is a comparison of experiences over different time periods</span>';
    }}

    // 3. Update Map Colorscale & Legend
    const colorscale = (currentYear === "change") ? metricObj.colorscale_change : metricObj.colorscale_year;
    let breakLabel = (currentScale === "jenks") ? "Natural Breaks (Jenks)" : "20% Equal Intervals";
    if (currentYear === "change") {{
      breakLabel = "Continuous Scale (-50% to +50%)";
    }}

    const colorbarTitle = `<b>${{datasetObj.legend_title}}</b><br><span style="font-size:11px;color:#6b7280">${{breakLabel}}</span>`;

    // Restyle Trace 0 (Choropleth)
    Plotly.restyle("disaster-map", {{
      z: [scaleObj.z],
      zmin: [scaleObj.zmin],
      zmax: [scaleObj.zmax],
      colorscale: [colorscale],
      customdata: [datasetObj.customdata],
      hovertemplate: [datasetObj.hovertemplate],
      "colorbar.tickvals": [scaleObj.tickvals],
      "colorbar.ticktext": [scaleObj.ticktext],
      "colorbar.title.text": [colorbarTitle]
    }}, [0]);

    // Restyle Trace 2 (Centered state label colors for contrast against dark bins)
    Plotly.restyle("disaster-map", {{
      "textfont.color": [scaleObj.textcolors]
    }}, [2]);
  }}

  document.querySelectorAll("#metric-buttons .btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
      document.querySelectorAll("#metric-buttons .btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentMetric = btn.getAttribute("data-metric");
      updateDashboard();
    }});
  }});

  document.querySelectorAll("#year-buttons .btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
      document.querySelectorAll("#year-buttons .btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentYear = btn.getAttribute("data-year");
      updateDashboard();
    }});
  }});

  document.querySelectorAll("#scale-buttons .btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
      if (btn.disabled) return;
      savedYearScale = btn.getAttribute("data-scale");
      currentScale = savedYearScale;
      updateDashboard();
    }});
  }});
</script>

</body>
</html>
"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print("SUCCESS! Saved index.html with pooled Jenks breaks, -50% to +50% shift scale, auto-contrasting labels, and corrected footer!")