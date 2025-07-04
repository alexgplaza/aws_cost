function compareMonths() {
    const current = document.getElementById("currentMonth").value;
    const compare = document.getElementById("compareMonth").value;

    fetch("/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current, compare })
    })
    .then(res => res.json())
    .then(data => {
      const tbody = document.getElementById("comparisonTableBody");
      tbody.innerHTML = "";

      data.forEach(row => {
        const diff = parseFloat(row.Difference || 0);
        const pct = parseFloat(row.Percentage || 0);

        const diffClass = diff > 0 ? "diff-positive" : "diff-negative";
        const pctClass = pct > 0 ? "diff-positive" : "diff-negative";

        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.Account}</td>
          <td class="${diffClass}">${diff.toFixed(2)}</td>
          <td class="${pctClass}">${pct.toFixed(2)}%</td>
        `;
        tbody.appendChild(tr);
      });

      document.getElementById("comparisonResults").style.display = "block";
    })
    .catch(error => {
      alert("Error comparing months. Please check the console for details.");
      console.error(error);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("accountSelector");
    if (selector) {
        selector.addEventListener("change", function () {
            const selected = this.value;

            fetch("/account_graph", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ account: selected })
            })
            .then(res => res.json())
            .then(data => {
                if (!data || !data.data) {
                    console.warn("No data for selected account");
                    return;
                }

                Plotly.newPlot("accountChartContainer", data.data, data.layout);
            })
            .catch(err => {
                console.error("Error fetching account data:", err);
            });
        });
    }

    if (typeof stackedBar !== "undefined") {
        Plotly.newPlot("stackedBarChart", stackedBar.data, stackedBar.layout);
    }
});
