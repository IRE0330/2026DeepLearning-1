"""Run from any directory after installing the package."""
import runpy
if __name__ == "__main__":
    runpy.run_module("cctv.examples.streamlit_app", run_name="__main__")
