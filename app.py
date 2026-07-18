# app.py — Hugging Face Spaces Entry Point (Streamlit SDK)
# =============================================================
# HF Spaces (Streamlit SDK) looks for a file named "app.py" at the
# root of the repository and runs:  streamlit run app.py
#
# This file simply re-exports the frontend by changing the working
# directory to backend/ (where main.py and all other modules live)
# so that the FastAPI auto-launcher inside frontend.py can import
# them correctly via "uvicorn main:app".
# =============================================================

import os
import sys

# Add backend/ to Python path so all imports work (config, pipeline, etc.)
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

# Now run the actual Streamlit frontend
exec(open(os.path.join(backend_dir, "frontend.py")).read())
