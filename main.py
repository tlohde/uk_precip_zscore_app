import pandas as pd
import streamlit as st
import altair as alt

# preamble
# useful dict for mapping full place names to code for url
region_dict = {
    'england & wales': 'EWP',
    'south east england': 'SEEP',
    'south west england & wales': 'SWEP',
    'central england': 'CEP',
    'north west england & wales': 'NWEP',
    'north east england': 'NEEP',
    'scotland': 'SP',
    'south scotland': 'SSP',
    'north scotland': 'NSP',
    'east scotland': 'ESP',
    'northern ireland': 'NIP'
    }


# get all the data for *all regions* and cahce it.
@st.cache_data
def get_data(region_dict):
    dfs = []
    for r in region_dict.keys():
        region = region_dict[r]
        baseurl = 'https://www.metoffice.gov.uk/hadobs/hadukp/data/daily/'
        filestr = f'Had{region}_daily_totals.txt'
        _tmp = pd.read_csv(
            baseurl+filestr,
            delim_whitespace=True,
            skiprows=[0, 1, 2],
            parse_dates=[0]).rename(columns={'Date': 'date',
                                             'Value': 'precip'})

        _tmp['region'] = r
        dfs.append(_tmp)

    df = pd.concat(dfs)
    df['doy'] = df['date'].dt.day_of_year
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year

    return df


# using the sliders to filter region, years to show,
# baseline period, and rolling window
# runs everytime you press 'go'
def filter_and_roll(df, regions, years, baseline, window):
    df = df.loc[df['region'].isin(regions)]
    rolling = (
        df
        .set_index('date')
        .groupby('region')['precip']
        .rolling(f'{window}d', min_periods=int(window/3))
        .sum()
        .rename('rolling_sum')
        )

    df = df.merge(rolling,
                  left_on=['region', 'date'],
                  right_index=True)

    idx = df.year.between(*baseline, inclusive='both')

    base_period = (
        df
        .loc[idx]
        .groupby(['region', 'doy'])['rolling_sum']
        .agg(['mean', 'std'])
        .reset_index()
        .rename(columns={'mean': 'base_mean_rolling_sum',
                         'std': 'base_std_rolling_sum'})
        )

    df = df.merge(base_period,
                  on=['region', 'doy'])

    df['z'] = (df['rolling_sum']
               - df['base_mean_rolling_sum']) / df['base_std_rolling_sum']

    return df.loc[df.year.between(*years)]


df = get_data(region_dict)

st.title('Precipitation anomalies')
st.write('data from: [HadUKP - UK regional precipitation series]\
    (https://www.metoffice.gov.uk/hadobs/hadukp/)')

with st.sidebar.form('pick'):
    regions = st.multiselect('Region(s)',
                             options=list(region_dict.keys()),
                             default=['scotland', 'england & wales'])

    years = st.select_slider('Year range (to show)',
                             options=list(range(df.year.min(),
                                                df.year.max()+1)),
                             value=(2021, 2024))

    baseline = st.select_slider('Climate baseline period\
        (should be ~30 years)',
                                options=list(range(df.year.min(),
                                                   df.year.max()+1)),
                                value=(1981, 2010))

    window = st.slider('Rolling window (days)',
                       min_value=7,
                       max_value=180,
                       value=30)

    submitted = st.form_submit_button('Make plot')
    if submitted:
        filtered = filter_and_roll(df, regions, years, baseline, window)

        selection = alt.selection_point(fields=['region'],
                                        bind='legend')
        scroll_x = alt.selection_interval(encodings=['x'],
                                          empty=False,
                                          bind='scales')
        lines = (
            alt.Chart(filtered, title='precipitation')
            .mark_line()
            .encode(
                alt.X('date').axis(title='date'),
                alt.Y('z').axis(title='z-score'),
                # x='date',
                # y='z',
                color=alt.condition(selection,
                                    'region:N',
                                    alt.value('lightgrey')),
                opacity=alt.condition(selection,
                                      alt.value(0.9),
                                      alt.value(0.1))
            ).add_params(selection, scroll_x)
            .properties(title='Precipitation anomalies')
        )

if submitted:
    st.altair_chart(lines, use_container_width=True)

st.write(
    '## How to use\n',
    '- select a region, or regions\n',
    '- choose the time period of interest\n',
    '- chose the baseline period (from which anomalies will be calculated)\n',
    '- select a time period (days) over which to sum precipitaiton\n',
    '- press _Make plot_\n\n',
    '### navigating the plot\n',
    '- if multiple regions have been selected, clicking on a single\
        region in the legend will highlight that series\n',
    '- zooming in only affects the date axis. panning left/right along\
        the date axis is possible\n',
    '### note\n',
    'if you display _all_ the data. any interactivity will be slow. so don\'t'
    )

st.write(
    '## Method\n',
    '- a rolling sum of precipitation is calculated over the specified number\
        of days (`rolling window`)\n',
    '\t - this is a measure of how much rain has fallen in the last 7 days,\
        or 30 days, or whatever...\n',
    '- for observations during the `baseline period`, the mean ($\mu$) and\
        standard deviation ($\sigma$) of\
        the rolling sum are computed for each day of the year\n'
    '- the z-score is computed by: $z = (p - \mu_d) / \sigma_d$\n',
    '\t - where $p$ is the measured precipitation \n',
    '\t - and $\mu_d$ and $\sigma_d$ are the mean and standard deviation for\
        _that_ day of the year'
)
