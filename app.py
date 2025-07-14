from flask import Flask, render_template, request, jsonify, Response
import pandas as pd
import plotly.graph_objs as go
import plotly
import json
import numpy as np
from datetime import datetime


app = Flask(__name__)
original_df = None  # global temporal para mantener los datos cargados (solo en memoria)

@app.route("/", methods=["GET", "POST"])
def index():
    global original_df
    table_data = None
    months = []
    periodo = None  # ✅ Aseguramos que siempre esté definida
    graphJSON = None
    accounts_list = []

    if request.method == "POST":
        file = request.files.get("file")
        if file:
            df = pd.read_csv(file)
            df.columns = df.columns.str.strip()

            for col in ['Usage Amount', 'Tax', 'Edp Discount']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            df["Usage Start Date"] = df["Usage Start Date"].astype(str).str.strip()
            df["Month"] = pd.to_datetime(df["Usage Start Date"], format="%d/%m/%Y", errors="coerce") \
                            .dt.to_period("M").astype(str)

            # Obtener rango de meses únicos
            meses_ordenados = sorted(df["Month"].dropna().unique())
            if meses_ordenados:
                periodo = f"{meses_ordenados[0]} a {meses_ordenados[-1]}"
            else:
                periodo = "Invalid date range"

            original_df = df.copy()

            df["Total"] = df["Usage Amount"] + df["Tax"] + df["Edp Discount"]
            summary = df.groupby("Account", as_index=False)["Total"].sum()
            summary.columns = ["Account", "Total Cost €"]
            summary["Total Cost €"] = summary["Total Cost €"].round(2)

            grand_total = summary["Total Cost €"].sum().round(2)
            summary.loc[len(summary.index)] = ["Grand Total", grand_total]

            table_data = summary.to_dict(orient="records")
            months = sorted(df["Month"].unique())
        
        if table_data:
            df_graph = original_df.copy()

            # Calcular coste total y extraer mes
            df_graph["Total"] = df_graph["Usage Amount"] + df_graph["Tax"] + df_graph["Edp Discount"]
            df_graph["Month"] = pd.to_datetime(df_graph["Usage Start Date"], format="%d/%m/%Y", errors="coerce") \
                                    .dt.to_period("M").astype(str)

            # Agrupar por mes y account
            grouped = df_graph.groupby(["Month", "Account"])["Total"].sum().reset_index()

            # Orden de meses
            months_ordered = sorted(grouped["Month"].unique())
            accounts = grouped["Account"].unique()

            # Colores por Account
            preset_colors = [
                 "#1f77b4",  # azul
   
       
                 "#9467bd",  # morado
        
                
                 "#17becf"   # turquesa
            ]


             # # preset_colors = [
            # #     "#1f77b4",  # azul
            # #     "#ff7f0e",  # naranja
            # #     "#2ca02c",  # verde
            # #     "#d62728",  # rojo
            # #     "#9467bd",  # morado
            # #     "#8c564b",  # marrón
            # #     "#e377c2",  # rosa
            # #     "#7f7f7f",  # gris
            # #     "#bcbd22",  # oliva
            # #     "#17becf"   # turquesa
            # # ]

            colors = {acc: preset_colors[i % len(preset_colors)] for i, acc in enumerate(accounts)}

            data = []

            # Trazas de barras por Account
            for acc in accounts:
                y_vals = []
                for month in months_ordered:
                    val = grouped[(grouped["Account"] == acc) & (grouped["Month"] == month)]["Total"].sum()
                    y_vals.append(val)
                data.append(go.Bar(
                    name=acc,
                    x=months_ordered,
                    y=y_vals,
                    marker=dict(color=colors.get(acc))
                ))

            # Percentiles (basado en total mensual global)
            monthly_totals = grouped.groupby("Month")["Total"].sum().values
            p50 = np.percentile(monthly_totals, 50)
            p90 = np.percentile(monthly_totals, 90)

            # Agregar líneas de percentil SOLO UNA VEZ
            data.append(go.Scatter(
                x=months_ordered,
                y=[p50] * len(months_ordered),
                mode='lines',
                name='Percentil 50',
                line=dict(color='blue', dash='dash'),
                showlegend=True
            ))

            data.append(go.Scatter(
                x=months_ordered,
                y=[p90] * len(months_ordered),
                mode='lines',
                name='Percentil 90',
                line=dict(color='red', dash='dash'),
                showlegend=True
            ))

            # Layout del gráfico
            layout = go.Layout(
                barmode='stack',
                title='Monthly Cost per AWS Account',
                xaxis=dict(title='Month', type='category'),
                yaxis=dict(title='Cost €'),
                legend=dict(orientation="h", y=-0.3)
            )

            fig = go.Figure(data=data, layout=layout)
            graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)           
        accounts_list = sorted(df_graph["Account"].dropna().unique().tolist())        
        
           
    return render_template("index.html", table_data=table_data, months=months, periodo=periodo, graphJSON=graphJSON,accounts=accounts_list)



@app.route("/compare", methods=["POST"])
def compare():
    global original_df
    data = request.get_json()
    current = data.get("current")
    compare = data.get("compare")

    if original_df is None or not current or not compare:
        return jsonify([])

    df = original_df.copy()
    df["Total"] = df["Usage Amount"] + df["Tax"] + df["Edp Discount"]

    # Agrupar por Account y mes
    grouped = df.groupby(["Account", "Month"])["Total"].sum().reset_index()

    current_df = grouped[grouped["Month"] == current].set_index("Account")["Total"]
    compare_df = grouped[grouped["Month"] == compare].set_index("Account")["Total"]

    all_accounts = current_df.index.union(compare_df.index)
    diff_df = pd.DataFrame(index=all_accounts)
    diff_df["Current"] = current_df
    diff_df["Compare"] = compare_df
    diff_df = diff_df.fillna(0)

    diff_df["Difference"] = (diff_df["Current"] - diff_df["Compare"]).round(2)

    # Calcular porcentaje de variación (con prevención de división por cero)
    def calculate_percentage(curr, comp):
        if comp == 0:
            return 0.0
        return round((curr - comp) / abs(comp) * 100, 2)

    diff_df["Percentage"] = [
        calculate_percentage(curr, comp)
        for curr, comp in zip(diff_df["Current"], diff_df["Compare"])
    ]

    diff_df = diff_df.reset_index()

    return jsonify(diff_df[["Account", "Difference", "Percentage"]].to_dict(orient="records"))

@app.route("/account_graph", methods=["POST"])
def account_graph():
    global original_df
    
    selected = request.json.get("account")
    if not selected or original_df is None:
        return jsonify({})

    df = original_df.copy()
    df["Total"] = df["Usage Amount"] + df["Tax"] + df["Edp Discount"]
    df["Month"] = pd.to_datetime(df["Usage Start Date"], format="%d/%m/%Y", errors="coerce") \
                    .dt.to_period("M").astype(str)

    df = df[df["Account"] == selected]

    if df.empty:
        return jsonify({})

    # Agrupar por mes y servicio
    grouped = df.groupby(["Month", "Service"])["Total"].sum().reset_index()

    # Calcular los 10 servicios más costosos en total
    top_services = grouped.groupby("Service")["Total"].sum().nlargest(10).index.tolist()

    # Reasignar el resto como 'Others'
    grouped["Service"] = grouped["Service"].apply(lambda s: s if s in top_services else "Others")

    # Agrupar de nuevo
    grouped = grouped.groupby(["Month", "Service"])["Total"].sum().reset_index()
    months = sorted(grouped["Month"].unique())
    services = grouped["Service"].unique()

    # Crear trazas
    data = []
    for service in services:
        y_vals = []
        for month in months:
            val = grouped[(grouped["Service"] == service) & (grouped["Month"] == month)]["Total"].sum()
            y_vals.append(val)
        data.append(go.Bar(name=service, x=months, y=y_vals))

    layout = go.Layout(
        barmode="stack",
        title=f"Monthly Breakdown Cost per Service for {selected}",
        xaxis=dict(title="Month", type="category"),
        yaxis=dict(title="Cost €"),
        legend=dict(orientation="h", y=-0.3)
    )

    fig = go.Figure(data=data, layout=layout)
    
    # === Gráfico DONUT para el último mes ===
    latest_month = df["Month"].max()
    df_last_month = df[df["Month"] == latest_month]

    # Agrupar por servicio y ordenar
    donut_data = df_last_month.groupby("Service")["Total"].sum().reset_index()
    donut_data = donut_data.sort_values("Total", ascending=False)


    # Limitar a top 10 y agrupar el resto como "Others"
    if len(donut_data) > 5:
        top_5 = donut_data.head(5)
        others_total = donut_data.iloc[5:]["Total"].sum()
        others_row = pd.DataFrame([{"Service": "Others", "Total": others_total}])
        donut_data = pd.concat([top_5, others_row], ignore_index=True)
    # Asegurarse de que los valores están bien formateados
    donut_data["Total"] = pd.to_numeric(donut_data["Total"], errors='coerce').fillna(0)

    # Crear gráfico
    # Crear gráfico DONUT (reemplaza esta parte)
    donut_fig = go.Figure(data=[go.Pie(
        labels=donut_data["Service"].tolist(),
        values=donut_data["Total"].astype(float).tolist(),
        hole=0.5,
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:.2f} € (%{percent})"
    )])
    donut_fig.update_layout(title=f"Service Cost Distributions for {selected} ({latest_month})")


    
    
    # Combinar ambos gráficos y serializar correctamente con PlotlyJSONEncoder
    combined_graphs = {
        #"stacked": fig.to_dict(),
        #"donut": donut_fig.to_dict()
        "stacked": json.loads(plotly.io.to_json(fig)),
        "donut": json.loads(plotly.io.to_json(donut_fig))

    }

    return Response(
        json.dumps(combined_graphs, cls=plotly.utils.PlotlyJSONEncoder),
        mimetype="application/json"
    )
    
from datetime import datetime

@app.route("/fiscal_usage", methods=["POST"])
def fiscal_usage():
    global original_df

    if original_df is None:
        return jsonify({"error": "No data uploaded"}), 400

    data = request.get_json()
    budget = data.get("budget")

    try:
        budget = float(budget)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid budget value"}), 400

    # Calcular rango fiscal: abril del año actual a marzo del siguiente
    now = datetime.now()
    fiscal_start = datetime(now.year, 4, 1)
    fiscal_end = datetime(now.year + 1, 3, 31)

    df = original_df.copy()

    # Convertir fechas
    df["DateParsed"] = pd.to_datetime(df["Usage Start Date"], format="%d/%m/%Y", errors="coerce")

    # Filtrar por el rango fiscal
    df_fiscal = df[(df["DateParsed"] >= fiscal_start) & (df["DateParsed"] <= fiscal_end)]

    # Calcular total
    df_fiscal["Total"] = df_fiscal["Usage Amount"] + df_fiscal["Tax"] + df_fiscal["Edp Discount"]
    total_spent = df_fiscal["Total"].sum()

    # Calcular porcentaje de uso
    used_pct = round((total_spent / budget) * 100, 2) if budget > 0 else 0.0

    return jsonify({
        "used_pct": used_pct,
        "total_spent": round(total_spent, 2)
    })





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
