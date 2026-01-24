# Inventory Optimization — Flask Deployment

Quick instructions to run the project locally or deploy to Streamlit Cloud.

Run locally:

```bash
python -m venv .venv
source .venv/Scripts/activate    # Windows
pip install -r requirements.txt
python app.py
```

Notes: The project uses `pulp` (an LP/MIP modelling package). For best performance, install a solver such as CBC. On Windows you can install `pulp` which bundles a CBC binary, or install CBC separately.
