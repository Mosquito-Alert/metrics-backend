import subprocess
from pathlib import Path


def generate_tiles(input_tif, output_dir, min_zoom=0, max_zoom=14, resampling="average"):
    """
    Generate XYZ tiles using GDAL's gdal2tiles.py.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        "gdal2tiles.py",
        "-z", f"{min_zoom}-{max_zoom}",
        "-r", resampling,
        "-w", "none",  # no HTML viewer
        input_tif,
        output_dir,
    ]
    subprocess.run(cmd, check=True)
