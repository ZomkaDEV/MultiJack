import os
import re
import shutil
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
)

from .localization import get_string


def recreate_directory_structure(src_dir, dest_dir, parent, logger):
    progress_dialog = QProgressDialog(
        get_string("processing"), "Cancel", 0, 100, parent
    )
    progress_dialog.setWindowTitle("MultiJack")
    progress_dialog.setMinimumWidth(400)
    progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress_dialog.setValue(0)
    progress_dialog.show()

    QApplication.processEvents()

    total_files = sum(len(files) for _, _, files in os.walk(src_dir))
    processed_files = 0
    operation_canceled = False

    for root, dirs, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)
        new_dest_dir = os.path.join(dest_dir, rel_path)
        os.makedirs(new_dest_dir, exist_ok=True)

    game = os.path.basename(os.path.normpath(src_dir))
    macos_path = os.path.join(src_dir, f"{game}.app", "Contents", "MacOS", game)

    for root, dirs, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)
        new_dest_dir = os.path.join(dest_dir, rel_path)

        for file in files:
            src_file = os.path.abspath(os.path.join(root, file))
            dest_file = os.path.join(new_dest_dir, file)

            if file.endswith("-log.txt"):
                continue

            try:
                if sys.platform == "darwin" and os.path.abspath(src_file) == macos_path:
                    if not os.path.exists(dest_file):
                        shutil.copy2(src_file, dest_file)
                        logger.info(f"Copied file: {src_file} -> {dest_file}")
                    else:
                        logger.warning(f"File already exists: {dest_file}")
                elif (
                    sys.platform == "linux"
                    and root == src_dir
                    and (file.endswith("_Vulkan") or file.endswith("_OpenGL"))
                ):
                    if not os.path.exists(dest_file):
                        shutil.copy2(src_file, dest_file)
                        logger.info(f"Copied file: {src_file} -> {dest_file}")
                    else:
                        logger.warning(f"File already exists: {dest_file}")
                else:
                    if not os.path.exists(dest_file):
                        os.symlink(src_file, dest_file)
                        if os.path.islink(dest_file) and os.path.exists(
                            os.readlink(dest_file)
                        ):
                            logger.info(f"Symlink created: {dest_file} -> {src_file}")
                        else:
                            logger.error(f"Failed to verify symlink: {dest_file}")
                    else:
                        logger.warning(f"Symlink already exists: {dest_file}")
            except OSError as e:
                logger.error(f"Error processing file {src_file} -> {dest_file}: {e}")

            processed_files += 1
            progress = int((processed_files / total_files) * 100)
            progress_dialog.setValue(progress)
            progress_dialog.setLabelText(
                f"{get_string('processing')}: {os.path.basename(src_file)}"
            )

            QApplication.processEvents()

            if progress_dialog.wasCanceled():
                operation_canceled = True
                logger.info("Operation canceled by user.")
                progress_dialog.close()
                return

    progress_dialog.setValue(100)
    progress_dialog.close()

    if operation_canceled:
        QMessageBox.warning(parent, "MultiJack", get_string("env_creation_failed"))


def validate_mod_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for dir_name in dirs:
            if any(
                dir_name.endswith(prefix) for prefix in ["games", "content", "videos"]
            ):
                return True
        for file_name in files:
            if any(
                file_name.endswith(prefix)
                for prefix in [".swf", ".jet", ".json", ".usm", ".swf"]
            ):
                return True
    return False


def check_folder_for_malicious_stuff(
    folder_path, game, install_location, parent, logger
):
    vanilla_game_path = os.path.join(install_location, game)

    if not os.path.exists(vanilla_game_path):
        logger.error(f"Vanilla game path not found: {vanilla_game_path}")
        return False

    executable_extensions = {".exe", ".dll", ".sh", ".dylib", "_Vulkan", "_OpenGL"}
    malicious_so_regex = re.compile(r"\.so(\.\d+)?$")

    vanilla_executables = set()
    for root, _, files in os.walk(vanilla_game_path):
        for file in files:
            if any(
                file.endswith(ext) for ext in executable_extensions
            ) or malicious_so_regex.search(file):
                relative_path = os.path.relpath(
                    os.path.join(root, file), vanilla_game_path
                )
                vanilla_executables.add(relative_path)

    for root, _, files in os.walk(folder_path):
        for file in files:
            if any(
                file.endswith(ext) for ext in executable_extensions
            ) or malicious_so_regex.search(file):
                relative_path = os.path.relpath(os.path.join(root, file), folder_path)

                if relative_path in vanilla_executables:
                    response = QMessageBox.question(
                        parent,
                        "MultiJack",
                        f"{get_string('mod_replaces_weird_files')}\n\n'{relative_path}'\n\n{get_string('do_you_want_to_continue')}",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )

                    if response == QMessageBox.StandardButton.No:
                        return True
    return False


def inject_mod_into_env(game, env_id, config_data, parent, logger):
    folder_path = QFileDialog.getExistingDirectory(
        parent, get_string("select_install_location")
    )

    if not folder_path:
        return

    if not validate_mod_folder(folder_path):
        if not sys.platform == "darwin":
            QMessageBox.warning(
                parent, "MultiJack", get_string("not_a_jackbox_mod_error")
            )
        else:
            QMessageBox.warning(
                parent, "MultiJack", get_string("not_a_jackbox_mod_error_macos")
            )
        return

    if check_folder_for_malicious_stuff(
        folder_path,
        game,
        config_data.get("install_location", ""),
        parent,
        logger,
    ):
        return

    env_path = os.path.join(config_data.get("env_location"), game, env_id)

    if sys.platform == "darwin":
        env_path = os.path.join(
            env_path, f"{game}.app", "Contents", "Resources", "macos"
        )

    if not os.path.exists(env_path):
        QMessageBox.warning(parent, "MultiJack", get_string("env_not_found_error"))
        return

    operation_canceled = False
    progress_dialog = QProgressDialog(
        get_string("injecting_files"), "Cancel", 0, 100, parent
    )
    progress_dialog.setWindowTitle("MultiJack")
    progress_dialog.setMinimumWidth(400)
    progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress_dialog.setValue(0)
    progress_dialog.show()

    total_files = sum(len(files) for _, _, files in os.walk(folder_path))
    processed_files = 0

    for root, _, files in os.walk(folder_path):
        rel_path = os.path.relpath(root, folder_path)
        dest_dir = os.path.join(env_path, rel_path)
        os.makedirs(dest_dir, exist_ok=True)

        for file in files:
            mod_file = os.path.join(root, file)
            dest_file = os.path.join(dest_dir, file)

            if os.path.islink(dest_file):
                logger.info(f"Removing existing symlink: {dest_file}")
                os.unlink(dest_file)

            if os.path.exists(dest_file):
                try:
                    if not os.path.samefile(mod_file, dest_file):
                        with open(mod_file, "rb") as f1, open(dest_file, "rb") as f2:
                            if f1.read() == f2.read():
                                logger.info(
                                    f"Files are identical, skipping: {dest_file}"
                                )
                                continue

                        relative_dest_file = os.path.relpath(dest_file, env_path)

                        response = QMessageBox.question(
                            parent,
                            "MultiJack",
                            get_string("mod_replaces_files")
                            + relative_dest_file
                            + "\n"
                            + get_string("do_you_want_to_continue"),
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )
                        if response == QMessageBox.StandardButton.No:
                            logger.info("Skipped conflicting mod")
                            operation_canceled = True
                            break

                        shutil.copy2(mod_file, dest_file)
                        logger.info(f"Overwritten: {relative_dest_file}")
                except Exception as e:
                    logger.error(
                        f"Error checking or overwriting file {mod_file} -> {dest_file}: {e}"
                    )
            else:
                try:
                    shutil.copy2(mod_file, dest_file)
                    logger.info(f"Copied: {dest_file}")
                except Exception as e:
                    logger.error(f"Error copying file {mod_file} -> {dest_file}: {e}")

            processed_files += 1
            progress = int((processed_files / total_files) * 100)
            progress_dialog.setValue(progress)
            progress_dialog.setLabelText(f"Processing: {os.path.basename(mod_file)}")

            QApplication.processEvents()

            if progress_dialog.wasCanceled():
                operation_canceled = True
                logger.info("Operation canceled by user.")
                progress_dialog.close()
                return

    progress_dialog.setValue(100)
    progress_dialog.close()

    if operation_canceled:
        QMessageBox.critical(parent, "MultiJack", get_string("mod_injection_failed"))
    else:
        QMessageBox.information(
            parent, "MultiJack", get_string("mod_injection_success")
        )
