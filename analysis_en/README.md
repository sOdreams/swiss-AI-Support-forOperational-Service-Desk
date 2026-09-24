# Swiss Life ticket analysis — English edition

This folder contains an English notebook and its executed results. It can be added to
the existing `data-exploratory` branch without changing the files already committed.

## What is included

- `Ticket_Exploratory_Analysis_Swiss_Life.ipynb`: explanations, code, outputs, and conclusions in English.
- `results/tables/`: 37 complete CSV tables with English headings and filenames.
- `results/charts/`: eight PNG charts with English titles and labels.
- `results/manifest.json`: input hash, package versions, coverage, and interpretation limits.
- `challenge_guidance.md`: the supplied challenge README, already written in English.
- `requirements.txt`: the libraries used by the analysis, plus JupyterLab.

The analysis uses all 20,000 tickets and 52,845 comments. It covers all 16 original
fields, missing values, repeated templates, routing, categories, dates, elapsed calendar
time to closure, and comment content. The notebook includes existing outputs, so it can
be read before rerunning it.

## Add this folder to your project

1. Extract `swiss_life_analysis_en.zip`.
2. Copy the extracted `analysis_en` folder into the repository root, alongside `frontend`.
   The archive contains that folder; do not add a second enclosing `analysis_en` directory.
3. Leave the existing analysis files in place. This folder has its own notebook and results.
4. Reuse `jira_first_20000_requested_fields_synthetic.json` from the repository root.
   The dataset is intentionally not duplicated in this package.

## Run the notebook

If your previous notebook runs successfully, use the same Python environment. From the
repository root, run:

```bash
jupyter lab analysis_en/Ticket_Exploratory_Analysis_Swiss_Life.ipynb
```

Select Python 3, then **Run → Run All Cells**. Keep the Jupyter terminal open while working.
The notebook also supports VS Code kernels that start in the repository root.

If you need a new Python environment, from the repository root run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r analysis_en/requirements.txt
python -m jupyterlab analysis_en/Ticket_Exploratory_Analysis_Swiss_Life.ipynb
```

The notebook looks for the JSON in its directory, its parent, and common input folders.
For another location, edit `DATA_FILE` in the configuration cell. Results are regenerated
inside `analysis_en/results/` under the documented folder layout.

The package was checked with Python 3.12, pandas 2.2.3, NumPy 2.3.5, Matplotlib 3.10.8,
and seaborn 0.13.2. Exact execution versions are also recorded in the manifest.

## Commit and push the English edition

Save the notebook before committing. Run these commands from the repository root on
`data-exploratory`, one step at a time:

```bash
git status --short --branch
git pull --ff-only origin data-exploratory
git add -- analysis_en/
git --no-pager diff --cached --stat
git commit -m "Add English ticket analysis notebook and results"
git push origin data-exploratory
git status --short --branch
```

If a command fails, stop and inspect its message before continuing. The resulting commit
adds the English folder. It does not undo the previous push or rewrite commit history.
The existing notebook and results remain available alongside this edition.

## Interpretation limits

The supplied challenge guidance says that Priority, Urgency, and Impact were sampled
randomly and independently of ticket content. Their recorded values are not valid
ground truth for training or evaluating real prioritization. Service labels and
historical assignments can also be incorrect or generic.

Time-to-closure statistics use synthetic calendar-day intervals for closed tickets with
valid dates. They are not SLA measurements or analyst effort. No model is trained, and
the separate 20-ticket challenge file is not included or evaluated.

All generated explanations, code comments, column names, chart labels, and filenames in
this folder are in English. Original source field names, category values, names, and
addresses are retained to preserve the data.
