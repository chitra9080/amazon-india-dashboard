"""Locate and read the Excel dataset.

The dataset path is built from this file's own location, so the app works no
matter which folder the command is run from.
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Union

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DATA_FILE = DATA_DIR / "Amazon_Sales_Data_India.xlsx"


class DataLoadError(Exception):
    """Raised when the dataset cannot be found or read."""


def get_default_data_path() -> Path:
    """Return the expected location of the dataset inside the project."""
    return DEFAULT_DATA_FILE


def load_raw_data(
    source: Union[str, Path, BinaryIO, None] = None, sheet_name: Union[int, str] = 0
) -> pd.DataFrame:
    """Read the Excel sheet exactly as stored (no cleaning).

    ``source`` may be a file path, an open binary file (for example an uploaded
    file) or ``None`` to use the default dataset location.
    """
    if source is None:
        source = DEFAULT_DATA_FILE

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise DataLoadError(
                f"Dataset not found at: {path}\n"
                f"Place 'Amazon_Sales_Data_India.xlsx' inside the 'data' folder "
                f"of the project, or upload the file from the dashboard."
            )
        source = path

    try:
        frame = pd.read_excel(source, sheet_name=sheet_name, engine="openpyxl")
    except Exception as error:  # noqa: BLE001 - re-raised with a friendly message
        raise DataLoadError(f"The Excel file could not be read: {error}") from error

    if frame.empty:
        raise DataLoadError("The Excel sheet was read successfully but contains no rows.")
    return frame
