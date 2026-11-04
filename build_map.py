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
# 3. PURE PYTHON CSV LOADER & POOLED JENKS CLASSIFIER
# ==============================================================================
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
# 5. LOAD DATASETS & PRECOMPUTE ALL COMBINATIONS + STATE DETAILS DICTIONARY
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
    colors = []
    for code in center_codes:
        val = z_vals[code_to_idx[code]]
        if not is_change:
            colors.append('#ffffff' if val >= 3.0 else '#111827')
        else:
            colors.append('#ffffff' if abs(val) >= 25.0 else '#111827')
    return colors

fixed_breaks = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
fixed_labels = ['0.0% – 20.0%', '20.1% – 40.0%', '40.1% – 60.0%', '60.1% – 80.0%', '80.1% – 100.0%']

views_data = {}
state_summary = {
    code: {'name': name, 'metrics': {}}
    for code, name in zip(state_codes, state_names)
}
metric_order = list(metrics.keys())

for metric_key, (val_col, count_col, q_text, hex_ramp) in metrics.items():
    pct_26, cnt_26 = get_percentage_and_count(rows_2026, val_col, count_col)
    pct_25, cnt_25 = get_percentage_and_count(rows_2025, val_col, count_col)

    pooled_series = (pct_26 + pct_25) if has_separate_2025 else pct_26
    pooled_jenks_breaks = fisher_jenks_breaks(pooled_series, k=5)
    labels_jenks = format_break_labels(pooled_jenks_breaks)

    pct_chg = []
    for i, (code, p26, p25, c26, c25) in enumerate(zip(state_codes, pct_26, pct_25, cnt_26, cnt_25)):
        if CHANGE_TYPE == 'relative':
            chg_26_vs_25 = round(((p26 - p25) / p25) * 100.0, 1) if p25 != 0 else 0.0
            chg_25_vs_26 = round(((p25 - p26) / p26) * 100.0, 1) if p26 != 0 else 0.0
        else:
            chg_26_vs_25 = round(p26 - p25, 1)
            chg_25_vs_26 = round(p25 - p26, 1)
        pct_chg.append(chg_26_vs_25)

        state_summary[code]['metrics'][metric_key] = {
            'p26': float(p26),
            'n26': int(c26),
            'p25': float(p25),
            'n25': int(c25),
            'diff_26_from_25': float(chg_26_vs_25),
            'diff_25_from_26': float(chg_25_vs_26)
        }

    chg_label_desc = "Relative % Change" if CHANGE_TYPE == 'relative' else "Percentage Point Shift"
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
            f'Question Respondents: n = %{{customdata[{n_col_idx}]:,.0f}}<br>'
            '<i>Click state to open detailed profile</i>'
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
        '2026: %{customdata[4]:.1f}% (n=%{customdata[2]:,.0f})<br>'
        '<i>Click state to open detailed profile</i>'
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
    padding: 20px 28px;
    background-color: #ffffff;
    color: #111827;
  }}
  .dashboard-container {{
    max-width: 1320px;
    margin: 0 auto;
    position: relative;
  }}

  /* Top Header Row with Title on Left and Methodology Button on Top Right */
  .top-header-row {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }}
  .main-title {{
    font-size: 30px;
    font-weight: 800;
    color: #111827;
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
  }}
  .methodology-btn {{
    appearance: none;
    background: #f9fafb;
    border: 1px solid #d1d5db;
    color: #374151;
    font-size: 12.5px;
    font-weight: 600;
    padding: 7px 13px;
    border-radius: 8px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    transition: all 0.15s ease;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  }}
  .methodology-btn:hover {{
    background: #f3f4f6;
    border-color: #9ca3af;
    color: #111827;
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
    margin: 0 0 16px 0;
  }}
  .subtext-note {{
    color: #dc2626;
    font-weight: 600;
    margin-left: 6px;
  }}

  /* Filter Bar */
  .controls-wrapper {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    align-items: center;
    justify-content: space-between;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 14px;
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
    font-size: 12.5px;
    font-weight: 500;
    padding: 6px 11px;
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

  /* Main Workspace: State Card hidden until a state is clicked */
  .main-workspace {{
    display: flex;
    align-items: stretch;
    gap: 18px;
    width: 100%;
  }}
  .state-card {{
    display: none; /* Hidden by default so map takes 100% width */
    width: 350px;
    flex-shrink: 0;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 16px 18px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    flex-direction: column;
    justify-content: space-between;
  }}
  .state-card.visible {{
    display: flex;
  }}
  .card-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    border-bottom: 2px solid #f3f4f6;
    padding-bottom: 10px;
    margin-bottom: 10px;
  }}
  .card-state-name {{
    font-size: 22px;
    font-weight: 800;
    color: #111827;
    margin: 0;
    line-height: 1.15;
  }}
  .card-view-badge {{
    display: inline-block;
    margin-top: 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #00a38d;
  }}
  .clear-btn {{
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    color: #4b5563;
    font-size: 11px;
    font-weight: 600;
    border-radius: 5px;
    padding: 4px 8px;
    cursor: pointer;
  }}
  .clear-btn:hover {{
    background: #e5e7eb;
    color: #111827;
  }}
  .card-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .card-table th {{
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #6b7280;
    text-align: left;
    padding: 6px 6px;
    border-bottom: 1px solid #e5e7eb;
  }}
  .card-table th.right, .card-table td.right {{
    text-align: right;
  }}
  .card-table td {{
    padding: 9px 6px;
    border-bottom: 1px solid #f3f4f6;
    font-size: 12.5px;
    vertical-align: middle;
  }}
  .card-table tr.active-metric-row {{
    background-color: #f0fdf9;
  }}
  .card-table tr.active-metric-row td:first-child {{
    border-left: 3px solid #00a38d;
    padding-left: 6px;
    font-weight: 700;
    color: #111827;
  }}
  .metric-name-cell {{
    font-weight: 600;
    color: #374151;
    line-height: 1.25;
  }}
  .metric-n-sub {{
    display: block;
    font-size: 11px;
    font-weight: 400;
    color: #6b7280;
    margin-top: 2px;
  }}
  .stat-primary {{
    font-size: 13.5px;
    font-weight: 700;
    color: #111827;
    white-space: nowrap;
  }}
  .stat-flow {{
    font-size: 12.5px;
    font-weight: 600;
    color: #1f2937;
    white-space: nowrap;
  }}
  .flow-arrow {{
    color: #6b7280;
    margin: 0 3px;
    font-weight: 700;
  }}
  .chg-up {{
    color: #dc2626;
    font-weight: 700;
    font-size: 12.5px;
    white-space: nowrap;
  }}
  .chg-down {{
    color: #2563eb;
    font-weight: 700;
    font-size: 12.5px;
    white-space: nowrap;
  }}
  .chg-flat {{
    color: #6b7280;
    font-weight: 600;
    font-size: 12px;
    white-space: nowrap;
  }}
  .card-footnote {{
    font-size: 11px;
    color: #6b7280;
    font-style: italic;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid #f3f4f6;
  }}

  .map-panel {{
    flex: 1;
    min-width: 0;
  }}
  #disaster-map {{
    width: 100%;
    height: 560px;
    cursor: pointer;
  }}

  /* Methodology Modal Popover */
  .modal-backdrop {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(17, 24, 39, 0.45);
    z-index: 9999;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  .modal-backdrop.open {{
    display: flex;
  }}
  .methodology-modal {{
    background: #ffffff;
    border-radius: 12px;
    max-width: 680px;
    width: 100%;
    padding: 24px 28px;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
    border: 1px solid #e5e7eb;
    max-height: 88vh;
    overflow-y: auto;
  }}
  .modal-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 12px;
    margin-bottom: 16px;
  }}
  .modal-title {{
    font-size: 20px;
    font-weight: 800;
    color: #111827;
    margin: 0;
  }}
  .modal-close-btn {{
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    color: #374151;
    font-size: 12px;
    font-weight: 700;
    border-radius: 6px;
    padding: 5px 10px;
    cursor: pointer;
  }}
  .modal-close-btn:hover {{
    background: #e5e7eb;
    color: #111827;
  }}
  .method-item {{
    margin-bottom: 16px;
    font-size: 13.5px;
    line-height: 1.55;
    color: #374151;
  }}
  .method-item:last-child {{
    margin-bottom: 0;
  }}
  .method-item strong {{
    color: #111827;
    font-weight: 700;
  }}
  .formula-box {{
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 8px 0;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 12.5px;
    color: #111827;
    text-align: center;
  }}

  @media (max-width: 980px) {{
    .main-workspace {{
      flex-direction: column;
    }}
    .state-card {{
      width: auto;
    }}
  }}

  .dashboard-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-top: 8px;
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
  <div class="top-header-row">
    <div>
      <h1 class="main-title">Experience with Disaster in the US</h1>
      <div class="question-subtitle" id="question-text">
        "Have You Personally Experienced <span class="question-highlight">Any Climate-Related Disaster</span> In The Last <span class="question-highlight">Twelve Months</span>?"
      </div>
      <div class="survey-subtext" id="survey-subtext">
        Nationally Representative Survey (n=1500), October 2026
      </div>
    </div>
    <button class="methodology-btn" id="open-methodology-btn">
      &#9432; Map Methodology
    </button>
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

  <!-- Side-by-Side Workspace: State Card stays hidden until a state is clicked -->
  <div class="main-workspace">
    <div class="state-card" id="state-card"></div>
    <div class="map-panel">
      <div id="disaster-map"></div>
    </div>
  </div>

  <div class="dashboard-footer">
    <div class="footer-source">
      Research Data: Surveys designed by CECE and administered with YouGov to a nationally representative sample (Oct 2025 &amp; 2026).
    </div>
    <img src="{LOGO_FILENAME}" alt="American University Center for Environment, Community & Equity" class="footer-logo" />
  </div>
</div>

<!-- Map Methodology Modal Card -->
<div class="modal-backdrop" id="methodology-modal-backdrop">
  <div class="methodology-modal" role="dialog" aria-labelledby="methodology-modal-title">
    <div class="modal-header">
      <h2 class="modal-title" id="methodology-modal-title">Methodology &amp; Map Calculations</h2>
      <button class="modal-close-btn" id="close-methodology-btn">&#10005; Close</button>
    </div>

    <div class="method-item">
      <strong>State-Level Percentages:</strong> Because respondents could skip individual hazard items on the survey, state percentages for each disaster category are calculated using the exact number of valid responses to that specific question in that state (<i>n</i><sub>question</sub>) rather than the overall state sample size:
      <div class="formula-box">
        State Percentage = (Respondents Experiencing Hazard / Total Valid Responses to Question) &times; 100
      </div>
    </div>

    <div class="method-item">
      <strong>Pooled Natural Breaks (Fisher-Jenks):</strong> When "Natural Breaks (Jenks)" is selected, states are grouped into 5 discrete classes using the Fisher-Jenks optimization algorithm. This method identifies natural groupings in the data by minimizing variance within each class and maximizing variance between classes. To allow direct visual comparison across years, break thresholds are calculated per disaster category using the pooled 2025 and 2026 state values&mdash;meaning the 5 color bins represent the exact same percentage ranges when toggling between 2025 and 2026.
    </div>

    <div class="method-item">
      <strong>Equal Intervals ("Interval/Scale"):</strong> For the 2025 and 2026 views, toggling to "Interval/Scale" switches the legend from data-driven clusters to 5 fixed 20% increments (0.0%&ndash;20.0%, 20.1%&ndash;40.0%, 40.1%&ndash;60.0%, 60.1%&ndash;80.0%, and 80.1%&ndash;100.0%), allowing direct comparison across different disaster types.
    </div>

    <div class="method-item">
      <strong>Percentage Point Shift (2025&ndash;2026):</strong> Rather than relative percent change (which exaggerates small baseline numbers), year-over-year change is measured as the arithmetic difference in percentage points between waves:
      <div class="formula-box">
        Percentage Point Shift = Percentage<sub>2026</sub> &minus; Percentage<sub>2025</sub>
      </div>
      For example, a state moving from 20.0% in 2025 to 30.0% in 2026 reflects a +10.0 percentage point shift. This view uses a continuous diverging color scale locked from &minus;50% to +50% (centered at 0%) and compares a 6-month recall window in October 2025 against a 12-month recall window in October 2026.
    </div>
  </div>
</div>

<script>
  const STATE_CODES = {json.dumps(state_codes)};
  const VIEWS_DATA = {json.dumps(views_data)};
  const STATE_SUMMARY = {json.dumps(state_summary)};
  const METRIC_ORDER = {json.dumps(metric_order)};
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
  let selectedState = null;

  const initMetricObj = VIEWS_DATA[currentMetric];
  const initDatasetObj = initMetricObj.datasets[currentYear];
  const initScaleObj = initDatasetObj[currentScale];

  // Trace 0: Base Choropleth Map
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
      thickness: 18,
      outlinewidth: 0
    }},
    hovertemplate: initDatasetObj.hovertemplate
  }};

  // Trace 1: Selected State Highlight Border Overlay
  const traceHighlight = {{
    type: "choropleth",
    locations: [],
    z: [],
    locationmode: "USA-states",
    colorscale: [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
    showscale: false,
    marker: {{ line: {{ color: "#111827", width: 3.2 }} }},
    hoverinfo: "skip"
  }};

  // Trace 2: Leader lines stopping at callout anchor points
  const traceLeaders = {{
    type: "scattergeo",
    lat: LEADER_LATS,
    lon: LEADER_LONS,
    mode: "lines",
    line: {{ width: 1.1, color: "#4b5563" }},
    hoverinfo: "skip",
    showlegend: false
  }};

  // Trace 3: Centered state abbreviations
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

  // Trace 4: Offset callout abbreviations
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
    margin: {{ l: 0, r: 10, t: 10, b: 10 }},
    paper_bgcolor: "white",
    height: 560
  }};

  Plotly.newPlot("disaster-map", [traceChoropleth, traceHighlight, traceLeaders, traceCenterLabels, traceCalloutLabels], layout, {{
    responsive: true,
    displayModeBar: false,
    scrollZoom: false,
    doubleClick: false
  }});

  const mapEl = document.getElementById("disaster-map");

  // Block wheel zoom on the SVG geo layer while allowing normal page scrolling
  mapEl.addEventListener("wheel", (e) => {{
    e.stopImmediatePropagation();
  }}, true);

  function formatChangeBadge(val) {{
    const rounded = Number(val.toFixed(1));
    if (rounded > 0) {{
      return `<span class="chg-up">&#9650; +${{rounded.toFixed(1)}}%</span>`;
    }} else if (rounded < 0) {{
      return `<span class="chg-down">&#9660; ${{rounded.toFixed(1)}}%</span>`;
    }} else {{
      return `<span class="chg-flat">&#8212; 0.0%</span>`;
    }}
  }}

  // Show/Hide Left State Card and resize map accordingly
  function renderStateCard() {{
    const cardEl = document.getElementById("state-card");

    if (!selectedState || !STATE_SUMMARY[selectedState]) {{
      cardEl.classList.remove("visible");
      cardEl.innerHTML = "";
      Plotly.Plots.resize(mapEl);
      return;
    }}

    cardEl.classList.add("visible");
    const stObj = STATE_SUMMARY[selectedState];
    let viewLabel = "";
    let col2Header = "";
    let col3Header = "";
    let footnoteText = "";

    if (currentYear === "2026") {{
      viewLabel = "October 2026 Survey Profile";
      col2Header = "2026 % (n)";
      col3Header = "vs. 2025";
      footnoteText = "Change shows percentage point shift from Oct 2025 to Oct 2026.";
    }} else if (currentYear === "2025") {{
      viewLabel = "October 2025 Survey Profile";
      col2Header = "2025 % (n)";
      col3Header = "vs. 2026";
      footnoteText = "Change shows percentage point difference in 2025 relative to 2026.";
    }} else {{
      viewLabel = "2025 &rarr; 2026 Shift Profile";
      col2Header = "2025 &rarr; 2026";
      col3Header = "Shift";
      footnoteText = "Compares 6-month recall (Oct 2025) vs. 12-month recall (Oct 2026).";
    }}

    let rowsHtml = "";
    METRIC_ORDER.forEach(mKey => {{
      const mStats = stObj.metrics[mKey];
      const isCurrent = (mKey === currentMetric) ? "active-metric-row" : "";

      if (currentYear === "2026") {{
        rowsHtml += `
          <tr class="${{isCurrent}}">
            <td>
              <div class="metric-name-cell">${{mKey}}</div>
              <span class="metric-n-sub">n = ${{mStats.n26.toLocaleString()}}</span>
            </td>
            <td class="right"><span class="stat-primary">${{mStats.p26.toFixed(1)}}%</span></td>
            <td class="right">${{formatChangeBadge(mStats.diff_26_from_25)}}</td>
          </tr>
        `;
      }} else if (currentYear === "2025") {{
        rowsHtml += `
          <tr class="${{isCurrent}}">
            <td>
              <div class="metric-name-cell">${{mKey}}</div>
              <span class="metric-n-sub">n = ${{mStats.n25.toLocaleString()}}</span>
            </td>
            <td class="right"><span class="stat-primary">${{mStats.p25.toFixed(1)}}%</span></td>
            <td class="right">${{formatChangeBadge(mStats.diff_25_from_26)}}</td>
          </tr>
        `;
      }} else {{
        rowsHtml += `
          <tr class="${{isCurrent}}">
            <td>
              <div class="metric-name-cell">${{mKey}}</div>
              <span class="metric-n-sub">n=${{mStats.n25}} &rarr; n=${{mStats.n26}}</span>
            </td>
            <td class="right">
              <span class="stat-flow">${{mStats.p25.toFixed(1)}}%<span class="flow-arrow">&rarr;</span>${{mStats.p26.toFixed(1)}}%</span>
            </td>
            <td class="right">${{formatChangeBadge(mStats.diff_26_from_25)}}</td>
          </tr>
        `;
      }}
    }});

    cardEl.innerHTML = `
      <div>
        <div class="card-header">
          <div>
            <h2 class="card-state-name">${{stObj.name}} (${{selectedState}})</h2>
            <span class="card-view-badge">${{viewLabel}}</span>
          </div>
          <button class="clear-btn" id="clear-state-btn" title="Close state card">&#10005; Clear</button>
        </div>
        <table class="card-table">
          <thead>
            <tr>
              <th>Disaster Type</th>
              <th class="right">${{col2Header}}</th>
              <th class="right">${{col3Header}}</th>
            </tr>
          </thead>
          <tbody>
            ${{rowsHtml}}
          </tbody>
        </table>
      </div>
      <div class="card-footnote">${{footnoteText}}</div>
    `;

    // Resize Plotly map so it fits cleanly next to the newly opened card
    Plotly.Plots.resize(mapEl);

    document.getElementById("clear-state-btn").addEventListener("click", () => {{
      selectedState = null;
      updateStateHighlight();
      renderStateCard();
    }});
  }}

  function updateStateHighlight() {{
    if (selectedState) {{
      Plotly.restyle("disaster-map", {{
        locations: [[selectedState]],
        z: [[1]]
      }}, [1]);
    }} else {{
      Plotly.restyle("disaster-map", {{
        locations: [[]],
        z: [[]]
      }}, [1]);
    }}
  }}

  mapEl.on("plotly_click", (data) => {{
    if (data && data.points && data.points.length > 0) {{
      const clickedLoc = data.points[0].location;
      if (clickedLoc) {{
        selectedState = (selectedState === clickedLoc) ? null : clickedLoc;
        updateStateHighlight();
        renderStateCard();
      }}
    }}
  }});

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

    let monthsText = "Twelve Months";
    if (currentYear === "2025") {{
      monthsText = "Six Months";
    }} else if (currentYear === "change") {{
      monthsText = "Six / Twelve Months";
    }}

    const qEl = document.getElementById("question-text");
    qEl.innerHTML = `"Have You Personally Experienced <span class="question-highlight">${{metricObj.question_text}}</span> In The Last <span class="question-highlight">${{monthsText}}</span>?"`;

    const subEl = document.getElementById("survey-subtext");
    if (currentYear === "2026") {{
      subEl.innerHTML = "Nationally Representative Survey (n=1500), October 2026";
    }} else if (currentYear === "2025") {{
      subEl.innerHTML = "Nationally Representative Survey (n=1500), October 2025";
    }} else {{
      subEl.innerHTML = 'Comparison of Nationally Representative Surveys (October 2025 vs. October 2026, n=1500) <span class="subtext-note">Note: this is a comparison of experiences over different time periods</span>';
    }}

    const colorscale = (currentYear === "change") ? metricObj.colorscale_change : metricObj.colorscale_year;
    let breakLabel = (currentScale === "jenks") ? "Natural Breaks (Jenks)" : "20% Equal Intervals";
    if (currentYear === "change") {{
      breakLabel = "Continuous Scale (-50% to +50%)";
    }}

    const colorbarTitle = `<b>${{datasetObj.legend_title}}</b><br><span style="font-size:11px;color:#6b7280">${{breakLabel}}</span>`;

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

    Plotly.restyle("disaster-map", {{
      "textfont.color": [scaleObj.textcolors]
    }}, [3]);

    if (selectedState) {{
      renderStateCard();
    }}
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

  // Methodology Modal Controls
  const modalBackdrop = document.getElementById("methodology-modal-backdrop");
  document.getElementById("open-methodology-btn").addEventListener("click", () => {{
    modalBackdrop.classList.add("open");
  }});
  document.getElementById("close-methodology-btn").addEventListener("click", () => {{
    modalBackdrop.classList.remove("open");
  }});
  modalBackdrop.addEventListener("click", (e) => {{
    if (e.target === modalBackdrop) {{
      modalBackdrop.classList.remove("open");
    }}
  }});
  document.addEventListener("keydown", (e) => {{
    if (e.key === "Escape" && modalBackdrop.classList.contains("open")) {{
      modalBackdrop.classList.remove("open");
    }}
  }});
</script>

</body>
</html>
"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print("SUCCESS! Saved index.html with collapsible State Card and top-right Map Methodology modal!")
