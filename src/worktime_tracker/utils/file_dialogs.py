"""Toga file-dialog helpers compatible with Android Storage Access Framework files."""

from pathlib import Path
import shutil
import toga


async def save_with_system_picker(window, source: Path, filename: str, file_types):
    target = await window.dialog(
        toga.SaveFileDialog(
            "選擇儲存位置", suggested_filename=filename, file_types=file_types
        )
    )
    if target is None:
        return None
    if hasattr(target, "open"):
        with source.open("rb") as input_file, target.open("wb") as output_file:
            shutil.copyfileobj(input_file, output_file)
        return target
    shutil.copyfile(source, Path(target))
    return Path(target)


async def open_with_system_picker(window, temporary_directory: Path, file_types):
    source = await window.dialog(
        toga.OpenFileDialog(
            "選擇工時管家備份", file_types=file_types, multiselect=False
        )
    )
    if source is None:
        return None
    if hasattr(source, "path") and source.path:
        return Path(source.path)
    if isinstance(source, (str, Path)):
        return Path(source)
    temporary_directory.mkdir(parents=True, exist_ok=True)
    destination = temporary_directory / "selected.worktimebackup"
    with source.open("rb") as input_file, destination.open("wb") as output_file:
        shutil.copyfileobj(input_file, output_file)
    return destination
