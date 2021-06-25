#!/usr/bin/python3
import kapitan
import commodore
import os
import shutil


def main():
    commodore_dir = os.path.dirname(commodore.__file__)
    kapitan_dir = os.path.dirname(kapitan.__file__)

    input_source_dir = os.path.join(commodore_dir, "helm_bindings", "inputs")
    input_target_dir = os.path.join(kapitan_dir, "inputs", "helm")

    dependency_manager_source_dir = os.path.join(commodore_dir, "helm_bindings", "dependency_manager")
    dependency_manager_target_dir = os.path.join(kapitan_dir, "dependency_manager", "helm")

    for f in ["helm_binding.py", "libtemplate.so"]:
        shutil.copyfile(os.path.join(input_source_dir, f),
                        os.path.join(input_target_dir, f))

    for f in ["helm_fetch_binding.py", "helm_fetch.so"]:
        shutil.copyfile(os.path.join(dependency_manager_source_dir, f),
                        os.path.join(dependency_manager_target_dir, f))


if __name__ == "__main__":
    main()