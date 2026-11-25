import plotly.graph_objects as go
from shiny import reactive
from shiny.express import input, ui
from shinywidgets import render_plotly

WEEKS = ["Jan 6", "Jan 13", "Jan 20", "Jan 27", "Feb 3", "Feb 10"]

METRICS = {
    "New accounts": {
        "Self-serve": [18, 22, 25, 24, 31, 29],
        "Sales-assisted": [6, 7, 9, 8, 11, 12],
    },
    "Churn rate": {
        "Self-serve": [3.1, 2.9, 3.4, 3.0, 2.6, 2.4],
        "Sales-assisted": [5.4, 5.1, 4.9, 5.2, 4.6, 4.4],
    },
}

SERIES_COLORS = {"Self-serve": "#007BC2", "Sales-assisted": "#1D1F21"}
AXIS_TITLES = {"New accounts": "New accounts", "Churn rate": "Churn rate (%)"}
HOVER = "<b>%{fullData.name}</b><br>%{x}: %{y}<extra></extra>"
LAYOUT = go.Layout(
    barmode="group",
    margin=dict(l=44, r=16, t=44, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, itemdoubleclick=False),
    font=dict(family="Open Sans, sans-serif", size=15, color="#1D1F21"),
)

ui.page_opts(title="", fillable=True)
ui.include_css("app.css")
ui.input_radio_buttons("metric", "Metric", list(METRICS))


@render_plotly
def chart():
    fig = go.FigureWidget(layout=LAYOUT.to_plotly_json())
    for name, values in METRICS["New accounts"].items():
        fig.add_bar(
            name=name,
            x=WEEKS,
            y=values,
            marker_color=SERIES_COLORS[name],
            hovertemplate=HOVER,
        )
    fig.update_xaxes(tickfont=dict(size=14), gridcolor="#E7E9EC")
    fig.update_yaxes(tickfont=dict(size=14), gridcolor="#E7E9EC", zeroline=False)
    return fig


@reactive.effect
def _():
    fig = chart.widget
    key = input.metric()
    vals = METRICS[key].values()
    for trace, y in zip(
        fig.data, vals
    ):
        trace.y = y
    fig.update_layout(yaxis_title=AXIS_TITLES[key])
