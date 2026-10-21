"""Source-checkout compatibility bridge; install cctv-analysis for distribution."""
from pathlib import Path
__path__ = [str(Path(__file__).resolve().parents[1] / 'cctv-analysis' / 'src' / 'cctv')]
from .api import AnalysisService, AnalysisJob, BusyError, OwnershipError
__all__ = ['AnalysisService', 'AnalysisJob', 'BusyError', 'OwnershipError']
