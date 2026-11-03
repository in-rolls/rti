"use strict";
const fields = ["state", "batch_id", "assigned_ra", "treatment"];
const labels = {plain: "Plain", legal_salience: "Legal salience"};
const elements = Object.fromEntries(fields.map(field => [field, document.getElementById(field)]));
const search = document.getElementById("search");
function cell(row, value) {
  const element = document.createElement("td");
  element.textContent = value;
  row.appendChild(element);
  return element;
}
Promise.all(["assignments", "instruments"].map(name => fetch(`data/${name}.json`).then(response => {
  if (!response.ok) throw new Error(`Could not load ${name}`);
  return response.json();
}))).then(([assignments, instruments]) => {
  for (const field of fields) {
    for (const value of [...new Set(assignments.map(row => row[field]))].sort()) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = labels[value] || value;
      elements[field].appendChild(option);
    }
  }
  function render() {
    const query = search.value.trim().toLocaleLowerCase();
    const visible = assignments.filter(row => fields.every(field => !elements[field].value || row[field] === elements[field].value)
      && `${row.application_id} ${row.office_name}`.toLocaleLowerCase().includes(query));
    const body = document.getElementById("rows");
    body.replaceChildren();
    for (const record of visible) {
      const row = document.createElement("tr");
      const identifier = cell(row, record.application_id);
      if (record.state_code === "TN") {
        const link = document.createElement("a");
        link.textContent = record.application_id;
        link.href = `batches/${encodeURIComponent(record.batch_id)}/applications/${encodeURIComponent(record.assigned_ra)}/${encodeURIComponent(record.application_id)}.txt`;
        identifier.replaceChildren(link);
      }
      for (const value of [record.state, record.office_name, record.batch_id, record.assigned_ra, labels[record.treatment]]) cell(row, value);
      body.appendChild(row);
    }
    document.getElementById("count").textContent = `${visible.length.toLocaleString()} of ${assignments.length.toLocaleString()} assignments`;
    const list = document.getElementById("instruments");
    list.replaceChildren();
    const batches = new Set(visible.map(row => row.batch_id));
    for (const instrument of instruments.filter(item => batches.has(item.batch_id))) {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.textContent = `${instrument.batch_id} · ${instrument.name}`;
      link.href = instrument.path;
      li.appendChild(link);
      list.appendChild(li);
    }
  }
  for (const element of [...Object.values(elements), search]) element.addEventListener("input", render);
  render();
}).catch(error => { document.getElementById("count").textContent = `Unable to load the worklist: ${error.message}. Please reload.`; });
