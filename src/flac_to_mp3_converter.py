from pathlib import Path
import subprocess
from .config import CLEANED_FLAC_PATH, CLEANED_MP3_PATH

class FlacToMp3Converter:
    def __init__(self, bitrate: str):
        self.bitrate = bitrate

    def convert(self, input_path: Path):
        """
        Converts all FLAC files in the input_path (recursively) to MP3,
        mirroring the directory structure from CLEANED_FLAC_PATH to CLEANED_MP3_PATH.
        """
        if not input_path.exists():
            print(f"Error: Input path '{input_path}' does not exist.")
            return

        try:
            relative_path = input_path.relative_to(CLEANED_FLAC_PATH)
        except ValueError:
            print(f"Error: Input path '{input_path}' is not within the CLEANED_FLAC_PATH.")
            return

        output_root_path = CLEANED_MP3_PATH / relative_path

        if input_path.is_file() and input_path.suffix.lower() == ".flac":
            # Handle single FLAC file conversion
            self._convert_single_flac(input_path, output_root_path)
        elif input_path.is_dir():
            # Handle directory (album or artist folder) conversion
            for flac_file in input_path.glob("**/*.flac"):
                self._convert_single_flac(flac_file, output_root_path, input_path)
        else:
            print(f"Error: Input path '{input_path}' is not a FLAC file or a directory.")

    def _convert_single_flac(self, flac_file: Path, output_root_path: Path, base_input_path: Path = None):
        """
        Converts a single FLAC file to MP3 using ffmpeg.
        """
        try:
            # Determine the relative path from the base_input_path to preserve structure
            if base_input_path:
                relative_path = flac_file.relative_to(base_input_path).parent
            else:
                relative_path = Path(".") # If no base_input_path, assume it's a direct file conversion

            output_dir = output_root_path / relative_path
            output_dir.mkdir(parents=True, exist_ok=True)

            mp3_file = output_dir / flac_file.with_suffix(".mp3").name

            if mp3_file.exists():
                print(f"Skipping {flac_file.name}: MP3 already exists.")
                return

            print(f"Converting {flac_file.name} to {mp3_file}...")
            
            command = [
                "ffmpeg",
                "-i", str(flac_file),
                "-codec:a", "libmp3lame",
            ]

            if self.bitrate.upper() == "V0":
                command.extend(["-q:a", "0"])
            else:
                command.extend(["-b:a", self.bitrate])
            
            command.append(str(mp3_file))
            
            # Run ffmpeg command
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            
            print(f"Successfully converted {flac_file.name}")
            # print(result.stdout) # Uncomment for ffmpeg output
            # print(result.stderr) # Uncomment for ffmpeg errors/warnings

        except subprocess.CalledProcessError as e:
            print(f"Error converting {flac_file.name} with ffmpeg: {e}")
            print(f"FFmpeg stdout: {e.stdout}")
            print(f"FFmpeg stderr: {e.stderr}")
        except Exception as e:
            print(f"An unexpected error occurred while converting {flac_file.name}: {e}")
